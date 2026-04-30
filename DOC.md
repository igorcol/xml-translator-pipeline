# Documentação Técnica — IDML Translation Engine

**Versão:** `v1.0.0-alpha.3`

---

## 1. Definição do Sistema

O sistema é um backend em Python orientado a microsserviços (construído sobre FastAPI e Asyncio) responsável pela extração, tradução em lote assistida por LLM e reconstrução de arquivos nativos do Adobe InDesign (`.idml`). O motor atua diretamente na camada XML do InDesign, isolando o texto das tags de design, aplicando paralelismo para tradução assíncrona, e remontando o pacote binário com 100% de preservação de layout.

---

## 2. Arquitetura do Sistema (DDD "Light")

A base de código foi estruturada isolando regras de negócio da camada de transporte HTTP:

- **`api/`** (Transporte/Web): Roteamento FastAPI, validação de inputs (`UploadFile`), e execução de background tasks.
- **`core/`** (Domínio): Onde reside o Engine. Contém os workers de extração (`extractor.py`), orquestração da IA (`translator.py`) e montagem de pacotes (`builder.py`).
- **`infra/`** (Persistência): Gerenciamento de I/O de disco e estado do banco de dados/cache (`cache_manager.py`).
- **`config/`** (Configuração): Injeção de dependências estáticas (como System Prompts de IA).

---

## 3. Fluxo de Vida da Requisição (End-to-End Pipeline)

O ciclo de vida de uma requisição `POST /api/v1/translate` segue uma pipeline estrita de 6 fases:

### Fase 1: Recepção e Isolamento de IO

- A API recebe um `multipart/form-data` contendo um buffer binário (`.idml`).
- Gera-se um hash UUID (`uuid.uuid4().hex[:8]`) anexado ao nome do arquivo.
- O buffer é salvo na memória de disco temporária (`data/input/`) com `shutil.copyfileobj`.

> **Insight:** O uso de UUID previne colisões de concorrência (Race Conditions) quando múltiplos usuários enviam payloads simultaneamente.

### Fase 2: Unpacking e Parsing XML (`IDMLExtractor`)

- O IDML é, na verdade, um pacote `.zip`. O extrator usa a biblioteca nativa `zipfile` para descompactar o arquivo em `temp_dir`.
- O motor mapeia o subdiretório `Stories/`, onde o InDesign armazena o texto real (arquivos `Story_*.xml`).
- O `lxml` carrega as árvores XML em memória (`self.xml_trees = dict`).
- **Bypass de Ruído (Crucial):** O InDesign fragmenta palavras em várias tags (`CharacterStyleRange`, `ParagraphStyleRange`) para aplicar formatações. O algoritmo mapeia exclusivamente nós folha que contêm `.text` utilizável, ignorando espaços em branco e caracteres invisíveis de diagramação.
- Gera-se um array de dicionários bidimensional:

```python
payload = [{"node": xml_element, "original_text": "string"}]
```

### Fase 3: Triagem de Memória de Tradução (Smart Caching)

- Antes de acionar a rede externa (LLM), o array `payload` passa por um interceptador local (`CacheManager`).
- Um banco de chave-valor em JSON carrega o histórico em memória RAM.
- Cada `original_text` é consultado via busca O(1).

**Split de Filas:** O sistema gera dois sub-arrays lógicos:

- **Resolvidos:** Textos localizados no cache recebem a tradução instantânea em memória (`final_translations[i] = cached`).
- **Pendentes:** Textos inéditos são empurrados para as listas de envio à IA (`pending_texts`, `pending_indices`).

> **Insight:** Essa arquitetura garante o bypass da API, reduzindo custos financeiros a zero para arquivos iterativos e transformando o tempo de processamento de minutos para < 2 segundos em casos de 100% de cache hit.

### Fase 4: O Motor de Tradução Assíncrono (`OpenAITranslator`)

Os itens "Pendentes" são processados de forma concorrente.

- **Batching:** As strings são divididas em chunks limitados (ex: lotes de 50 strings). O envio de arrays permite que a IA deduza o contexto macro do documento.
- **Concurrency Control:** Um `asyncio.Semaphore(5)` restringe a execução para no máximo 5 chamadas simultâneas à API externa, evitando banimentos por Rate Limit (HTTP 429).
- **Execução via `asyncio.gather`:** As coroutines disparam simultaneamente e o Python cede a thread enquanto aguarda o I/O da rede.

**O Mecanismo de Auto-Cura e Degradação Graciosa (Sniper Mode):**

- **O Problema (O Anti-Padrão da "IA Prestativa"):** Ocasionalmente, o InDesign fragmenta uma única frase em múltiplos nós XML (ex: quando uma palavra no meio da frase possui uma formatação distinta). O LLM, treinado para gerar linguagem natural coerente, recebe o array fragmentado e tenta "corrigir", fundindo os itens em uma string única (Ex: Input de 50 itens gera um Output de 49). Isso quebra a paridade 1:1 estritamente necessária para a injeção reversa no XML.

- **Defesa de Nível 1 (Prompt Engineering):** O System Prompt no config/prompts.py força regras estritas de não-concatenação e preservação de fragmentos isolados, atuando como a primeira barreira.

- **Defesa de Nível 2 (Exponential Backoff):** Se o worker avalia len(input) != len(output), a classe captura a exceção, realiza o dump do I/O conflitante para auditoria interna (debug_desync.json), e engatilha um loop recursivo com atraso exponencial (wait = 2 ** attempt).

- **Defesa de Nível 3 (Ultimate Fallback - Sniper Mode):** Se um lote falha por 3 tentativas consecutivas, o orquestrador assume que a amostra possui um viés irrecuperável na IA em modo batch. O sistema interrompe o fluxo normal e degrada graciosamente para o Modo Sniper. O lote de 50 é desmembrado e enviado em chamadas unitárias (1-by-1). Como o input passa a ser 1, uma dessincronização de array torna-se impossível. O sistema absorve o impacto temporal da rede, mas garante 100% de integridade estrutural ao artefato final.

### Fase 5: Injeção Reversa e Reconstrução (`IDMLBuilder`)

- Após a resolução de todas as coroutines, os dados retornados são salvos no cache SSD para usos futuros.
- O orquestrador passa o vetor preenchido (`final_translations`) para a classe de Build.
- Iterando paralelamente sobre o payload e os resultados, a injeção ocorre pela alteração da propriedade `node.text = translations[i]`.

> **Insight de Segurança de Layout:** Como a referência original do nó (em memória heap) foi guardada desde a Fase 2, alterar `node.text` modifica o atributo diretamente na árvore do `lxml`, sem tocar nas tags de envoltório (`<ParagraphStyleRange>`). Fontes, alinhamentos e kerning permanecem imaculados.

- O script sobrescreve os `Story_*.xml` físicos com as novas árvores em UTF-8.
- A função `repackage()` comprime o diretório de volta usando `zipfile.ZIP_DEFLATED`.

### Fase 6: Retorno e Protocolo de Auto-Limpeza

- A API devolve um construto de fluxo HTTP: `FileResponse(media_type="application/octet-stream")`, induzindo o cliente (browser/aplicação) a forçar o download.
- O serviço injeta uma rotina não-bloqueante via FastAPI `BackgroundTasks`.
- Imediatamente após a entrega do stream binário ao usuário, a thread de background entra em ação (`cleanup_temp_files`), deletando com `os.remove()` os pacotes físicos brutos (IDML input/output) do disco local.

> **Insight:** Isso neutraliza riscos de Storage Overflow do servidor e garante conformidade de segurança (GDPR/LGPD), pois documentos de clientes nunca persistem ociosamente na máquina; apenas os fragmentos descontextualizados permanecem no cache local de TM (Translation Memory).

---

## 4. Desafios Técnicos & Engenharia de Soluções

O problema mais difícil do projeto não foi parsear XML — foi dobrar uma LLM probabilística pra se comportar como função determinística sobre fragmentos sem contexto.

### 4.1 O Problema: Fragmentação de Contexto

O InDesign armazena texto de forma visual, não lógica. Uma frase como `"Save photos and videos to show your family later!"` é dividida em múltiplos nós `<Content>` isolados por causa de quebras de linha ou variações sutis de formatação. Sem visibilidade do todo, a IA traduz cada fragmento literal e isoladamente, e a remontagem produz português quebrado.

### 4.2 Abordagem Descartada: Agrupamento por Separadores

A primeira ideia foi concatenar fragmentos do mesmo `ParagraphStyleRange` com um delimitador (`fragmento_1 ||| fragmento_2`) e fazer split do retorno. Descartada antes de virar código por dois motivos:

- **Inversão sintática EN→PT.** Em `"the |||red||| car"` → `"o carro |||vermelho|||"`, a posição do delimitador é trocada pela tradução. A injeção reversa colocaria texto no nó XML errado, quebrando a relação entre conteúdo e formatação.
- **Viola o contrato arquitetural.** O `IDMLBuilder` opera sob a premissa "nó-folha = unidade atômica, mutação in-place". Agrupar fragmentos forçaria refatoração do Builder e do cache.

A decisão foi não codar a solução errada e partir direto pra abordagem que preserva a arquitetura.

### 4.3 Solução em Três Camadas

**Camada 1 — Extração com contexto via XPath.** Cada nó-folha sobe na árvore (`ancestor::ParagraphStyleRange`) e captura a frase semântica completa do parágrafo. O payload deixa de ser string crua e vira objeto contextual:

```python
{"texto_alvo": "videos to show", "contexto_macro": "Save photos and videos to show your family later!"}
```

O `texto_alvo` continua sendo o único alvo de tradução e única chave de cache. O `contexto_macro` é metadado de leitura — alimenta a IA com base gramatical sem afetar o cache hit rate.

**Camada 2 — ID Mapping Relacional.** Com payload mais rico, a IA passou a alucinar cardinalidade ocasionalmente (52 traduções pra 50 inputs). Solução: cada fragmento ganha um `id`, e a IA é obrigada a devolver `{"translations": {"1": "...", "2": "..."}}`. Qualquer id faltando, extra ou inventado é detectado deterministicamente. O Sniper Mode permanece como rede final, mas raramente é acionado depois dessa mudança.

**Camada 3 — Few-Shot com Anti-Padrão.** Mesmo com contexto, a IA mantinha tradução literal e isolada do fragmento, ignorando regência verbal. `"videos to show"` + `"your family later"` virava `"vídeos para mostrar"` + `"sua família depois"` — corretos isoladamente, mas a junção `"mostrar sua família"` está gramaticalmente errada (verbo "mostrar" exige preposição). Solução: instrumentar o prompt com exemplo negativo e positivo lado a lado, autorizando explicitamente a injeção de conectivos (preposições, artigos) no fragmento certo. Modelos generativos respondem melhor a padrão concreto que a regra textual.

### 4.4 Resultado

A combinação das três camadas transformou a LLM de worker probabilístico em função quase-determinística pra tradução técnica fragmentada. A arquitetura original (nó-folha como unidade atômica, mutação in-place, IDMLBuilder intacto) foi preservada — toda a evolução aconteceu nas camadas de extração e prompting.

---
