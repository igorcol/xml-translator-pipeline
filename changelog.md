# Changelog

Todas as mudanças notáveis neste projeto serão documentadas neste arquivo.

O formato baseia-se em [Keep a Changelog](https://keepachangelog.com/), e este projeto adere ao [Versionamento Semântico](https://semver.org/lang/pt-BR/).

---
## [1.0.0-alpha.3]

### Added
- **Context-Aware Translation:** O extrator agora mapeia a árvore XML (`ParagraphStyleRange`) para capturar e enviar o parágrafo completo (`contexto_macro`) como contexto de leitura para a IA.
- **ID Mapping Relacional:** Implementação de um sistema de chaves (IDs) atreladas ao payload, forçando a IA a manter uma paridade determinística 1-para-1 na resposta e inviabilizando alucinações de quantidade.
- **Interceptador de Ruído Nativo:** Bypass algorítmico (antes da chamada da API) que identifica e ignora strings contendo apenas pontuação ou espaços em branco, economizando tokens e evitando falsos positivos.
- **Sistema de Diagnóstico Silencioso:** Criação da função `_dump_diagnostic` para interceptar e salvar os dados brutos de entrada/saída da IA em arquivos `.json` focados em auditoria (debug).

### Changed
- **Engenharia do System Prompt:** Reescrita total das regras de saída para exigir objetos JSON estruturados.
- **Few-Shot Prompting Gramatical:** Adição de exemplos de antipadrões no prompt para forçar a IA a injetar preposições e "cola gramatical" na tradução baseada no contexto fornecido.
- **Arquitetura de Payload Tridimensional:** A transição de dados entre o Motor, CLI e Rotas Web deixou de usar arrays de strings soltas para utilizar dicionários (`id`, `texto_alvo`, `contexto_macro`), mantendo a busca no Cache nativo em O(1).

### Fixed
- Erro fatal de Dessincronização de Lotes ("desync"), onde a LLM aglutinava ou desmembrava frases e retornava arrays com tamanhos incorretos (ex: devolvendo 52 itens em um lote de 50).
- Quebra de sistema por falha de serialização (`Object of type _Element is not JSON serializable`), isolando e limpando os nós complexos do `lxml` antes de submetê-los aos métodos da biblioteca `json`.

---
## [1.0.0-alpha.2] - Self-Healing Absoluto (Sniper Mode)

### Adicionado
- **Modo Sniper (Ultimate Fallback):** Implementação de um mecanismo de degradação graciosa no `OpenAITranslator`. Quando um lote falha o limite máximo de retentativas (3x) por dessincronização, o motor não aborta mais a requisição. Ele quebra o lote e realiza chamadas individuais (1-by-1) para a API, garantindo 100% de sucesso na sincronia do XML sem interromper o fluxo do arquivo.

### Corrigido
- **System Prompt Strict Rules:** Adição de travas de segurança explícitas no `config/prompts.py` (Persona) proibindo a IA de fundir ou concatenar fragmentos isolados (ex: strings que contêm apenas uma palavra ou pontuação), mitigando o comportamento "prestativo" do LLM de tentar consertar quebras visuais do InDesign.
---

## [1.0.0-alpha.1] — Motor Web Isolado (Core Engine API)

Este é o primeiro grande marco arquitetural. O projeto deixou de ser um script de linha de comando estrito e evoluiu para um ecossistema de microsserviços preparado para consumo via Front-end (Next.js).

### Adicionado

- **FastAPI Foundation:** Implementação da camada web de alta performance com rotas isoladas (`api/routes.py`), documentação automática via Swagger e middleware de CORS ativado.
- **Protocolo de Auto-Limpeza (Storage Management):** Integração do `BackgroundTasks` para exclusão assíncrona e silenciosa de binários `.idml` de entrada e saída imediatamente após o download, garantindo escalabilidade de disco no servidor.
- **Endpoint `POST /api/v1/translate`:** Interface de contrato para receber pacotes em `multipart/form-data`, ativando o pipeline de extração e devolvendo um `FileResponse` em `octet-stream` para download direto.
- **Variável de Ambiente `DEBUG_MODE`:** Flag estratégica na API para reter arquivos temporários no disco durante o desenvolvimento e depuração.

### Modificado

- **Domain-Driven Design (DDD):** Reestruturação total de diretórios. O motor foi segmentado em `core/` (regras de negócio), `api/` (transporte web), `infra/` (persistência) e `config/` (parâmetros de IA).
- **Tratamento do CLI:** O antigo arquivo `main.py` foi preservado e renomeado para `cli.py`, servindo agora exclusivamente como uma ferramenta administrativa (Porta dos Fundos) para processamento em massa e bypass da camada HTTP.
- **Roteamento de Arquivos Locais:** Ajuste na criação automática de diretórios temporários (`data/input/`, `data/output/`, `data/cache/`) e adoção de injeção de IDs únicos (`uuid4`) para evitar colisões de concorrência.

---

## [0.9.1] — Pré-Release (CLI Translation Pipeline)

A fundação lógica e algoritmos de processamento de linguagem natural construídos como um script local de execução pontual.

### Adicionado

- **`IDMLExtractor`:** Algoritmo de bypass de injeção XML usando `lxml` para isolar estritamente o texto de diagramação (`CharacterStyleRange`), prevenindo gasto de tokens e a quebra do layout original.
- **Memória de Tradução Local (Smart Caching):** Implementação de interceptador O(1) ancorado em um JSON estático. Redução de chamadas recursivas para strings repetidas, promovendo Zero Latency e corte drástico de custos da API.
- **Motor de Orquestração Assíncrona:** Uso de `asyncio` e semáforos concêntricos para processamento de filas em lote (Batching de 50 strings e concorrência máxima de 5 requisições paralelas).
- **Self-Healing Algorithm:** Loop interno de estabilização (Exponential Backoff) que intercepta dessincronização de JSON gerado pela IA, realizando dumps de auditoria e forçando correção autônoma sem interromper a rotina de execução.
- **`IDMLBuilder`:** Módulo de reconstrução estrutural para zipar a árvore XML e gerar o artefato binário pronto para abertura no Adobe InDesign.