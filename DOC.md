# Documentação Técnica — IDML Translation Engine

**Versão:** `v1.0.0-alpha.2`

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

## 4. Destaques do Código (Chaves de Engenharia)

- **Type Hinting & Pydantic:** Código fracamente acoplado e estritamente tipado, garantindo validação de extensões e schemas nativos de request.
- **Proteção de Mutabilidade (Split Brain Avoidance):** Atualizações do vetor final acontecem em uma lista pré-alocada (`[None] * len(payload)`), cujos índices foram salvos durante o desvio de memória na Triagem. Isso permite assincronismo desenfreado sem colisão de estado (race conditions na alocação da resposta).
- **Modularidade:** A troca futura do modelo em cache JSON atual por um PostgreSQL/Redis/Supabase demanda a refatoração de apenas 1 arquivo (`cache_manager.py`), não exigindo intervenção no core do domínio.