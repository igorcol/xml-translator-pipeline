# Changelog

Todas as mudanças notáveis neste projeto serão documentadas neste arquivo.

O formato baseia-se em [Keep a Changelog](https://keepachangelog.com/), e este projeto adere ao [Versionamento Semântico](https://semver.org/lang/pt-BR/).

---
## [1.0.0-alpha.1.2]

### Fixed

- **Persona**
- **Transaltor 1-by-1 sniper lá do bgl (n sei se fica em fixxed ou em added)**
    No doc.md ou readme adicionar sobre isso, e como resolvemos por enquanto.

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