# IDML Translation Engine

Backend em Python que traduz arquivos nativos do Adobe InDesign (`.idml`) com LLM, preservando 100% do layout original. Construí porque um freela me consumiu 5 horas de cliques manuais que poderiam ter sido 5 minutos.

---

## O que originou

Peguei um freelance de tradução de manual técnico, EN → PT, 1.600+ linhas em arquivo `.idml`. O fluxo padrão de quem faz esse tipo de trabalho:

1. Abre o arquivo no OmegaT (CAT tool)
2. Copia uma linha
3. Cola no Gemini/ChatGPT
4. Espera tradução
5. Copia a tradução
6. Cola de volta no OmegaT
7. Repete 1.599 vezes

Otimizei com macros do AutoHotKey e ainda assim levava horas. Erro humano em cada passo.

A pergunta óbvia: por que mexer na interface? O `.idml` é um formato XML. Dá pra abrir, extrair texto, mandar pra LLM em lote, e remontar.

Construí.

---

## O que faz

`POST /api/v1/translate` recebe um `.idml`, devolve um `.idml` traduzido. Layout, fontes, kerning e estilos ficam intactos. Tradução em lote via LLM com cache de Translation Memory que zera custo em iterações.

Pipeline em 6 fases assíncronas, com auto-cura quando a LLM falha.

---

## Arquitetura

```
┌─────────────────┐
│ POST /translate │  Upload .idml + UUID hash
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────────────┐
│  Fase 1 — Recepção e isolamento de I/O          │
│  Fase 2 — Unzip + parse XML (lxml)              │
│  Fase 3 — Triagem via TM cache (split de filas) │
│  Fase 4 — Tradução assíncrona com self-healing  │
│  Fase 5 — Injeção reversa + repackage           │
│  Fase 6 — Stream de resposta + auto-cleanup     │
└─────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────┐
│ .idml traduzido │  FileResponse + cleanup background
└─────────────────┘
```

Estrutura do código segue DDD light:

```
api/    → roteamento FastAPI, validação, background tasks
core/   → extractor, translator, builder (regra de negócio)
infra/  → cache_manager, I/O de disco
config/ → system prompts da IA, settings
```

A separação não é cosmética. O cache hoje é JSON em RAM. Migrar pra Redis ou Postgres exige refatorar 1 arquivo (`infra/cache_manager.py`). O domínio não sabe nem se importa onde os dados moram.

---

## Engenharia de resiliência (o coração do sistema)

LLM não é função pura. Mando 50 strings, ela me devolve 49 porque resumiu duas linhas parecidas em uma. Mando outras 50, ela une três. É probabilístico. Quem coloca LLM em produção sem tratar isso vai ter dessincronização de payload em algum momento, e quando isso acontece o sistema inteiro corrompe silenciosamente.

Construí um circuito de auto-cura:

```python
# Pseudocódigo do worker
async def translate_batch(strings: list[str]) -> list[str]:
    for attempt in range(MAX_RETRIES):
        result = await call_llm(strings)
        if len(result) == len(strings):
            return result
        # Dessync detectada
        dump_for_audit(strings, result, attempt)
        await asyncio.sleep(2 ** attempt)  # exponential backoff
    raise PayloadDesyncError(...)
```

O que esse circuito garante:

- **Detecção determinística** via assert de cardinalidade. Não confio no que a LLM diz que fez, conto o que ela entregou.
- **Auditoria automática** de cada falha em `debug_desync.json` pra eu poder analisar padrões depois.
- **Backoff exponencial** entre tentativas - 1s, 2s, 4s. Dá tempo do modelo "esfriar" e reduz pressão em rate limit.
- **Convergência forçada** - em 3-4 tentativas a LLM acerta o len. Não vi um caso real de payload que não convergiu até hoje.

Esse é o pedaço do sistema que mais aprendi construindo. Tratar LLM como worker não-determinístico que falha de formas previsíveis muda como você projeta tudo em volta.

---

## Bypass do XML do InDesign

Um `.idml` é um zip. Dentro tem uma pasta `Stories/` com arquivos XML que representam o texto. O problema: o InDesign não guarda "uma palavra por nó". Ele fragmenta texto em dezenas de tags de estilo encadeadas. Uma frase de 5 palavras pode virar 12 elementos `<CharacterStyleRange>` aninhados, com espaços em branco e separadores invisíveis no meio.

Se você manda tudo isso pra LLM, três coisas quebram ao mesmo tempo: o token cost explode, o contexto vira ruído, e o retorno não tem como ser remontado.

A solução foi mapear apenas **nós-folha com `.text` utilizável** e ignorar o resto:

```python
# Extrator percorre a árvore lxml
for element in tree.iter():
    if element.text and element.text.strip():
        if not is_layout_noise(element):
            payload.append({
                "node": element,           # referência heap preservada
                "original_text": element.text
            })
```

A chave dessa abordagem está em `"node": element`. Eu guardo a referência ao objeto Python, não uma cópia. Quando o lote volta da LLM traduzido, faço `node.text = translation[i]` e a árvore inteira do lxml é mutada in-place. As tags de estilo, fontes, kerning, alinhamento. Tudo isso continua exatamente como estava porque eu nunca toquei nesses atributos.

O designer abre o arquivo final no InDesign e não vê uma vírgula fora do lugar. Isso só funciona porque o sistema decidiu desde o início **operar abaixo da camada que o InDesign tenta proteger**, em vez de tentar replicar o que ele faz.

---

## Controle de custo e concorrência

Três decisões que separam protótipo de coisa que dá pra rodar 1.000 vezes sem quebrar nem quebrar a conta:

**TM cache antes da LLM.** Toda string passa por um cache de Translation Memory (chave-valor em JSON, busca O(1)) antes de virar chamada de API. Strings já vistas resolvem em RAM. Em arquivos iterativos (cliente que manda revisão do mesmo manual), 100% de cache hit zera custo da Fase 4 e o tempo de processamento cai pra menos de 2 segundos.

**Semáforo controlando concorrência.** `asyncio.Semaphore(5)` limita pra 5 chamadas simultâneas à API externa. O `asyncio.gather` dispara o lote, o semáforo segura o que excede. Resultado: throughput alto sem disparar rate limit (HTTP 429) que banem a chave por horas.

**Batching de 50 strings por chamada.** Em vez de 50 chamadas com 1 string cada, faço 1 chamada com array de 50. A LLM ganha contexto macro do documento (melhora a qualidade da tradução técnica) e o overhead de rede cai 50x. O trade-off é que aumenta a chance de dessincronização. Daí a necessidade do circuito de self-healing acima.

**Auto-cleanup pós-stream.** Depois que o `FileResponse` entrega o `.idml` traduzido, uma `BackgroundTask` do FastAPI deleta os arquivos brutos do disco. Documentos de cliente nunca persistem ociosos. Só o cache de TM (que armazena fragmentos descontextualizados) fica.

---

## Stack

Python 3.11 · FastAPI · asyncio · lxml · Pydantic · OpenAI/Gemini SDK · zipfile (stdlib)

---

## Setup

```bash
git clone https://github.com/igorcol/xml-translator-pipeline.git && cd xml-translation-pipeline
pip install -r requirements.txt
echo "GEMINI_API_KEY=sua_chave" > .env
uvicorn api.main:app --reload
```

Endpoint disponível em `localhost:8000/api/v1/translate`.

---

## Status

`v1.0.0-beta.1`. Em uso real pra projetos de tradução técnica. Arquitetura projetada pra evoluir pra serviço multi-tenant, fila de jobs, dashboard de TM compartilhada por cliente, billing por volume traduzido. Mercado óbvio: agências de tradução técnica e editoras que trabalham com manuais industriais em InDesign e hoje fazem o mesmo fluxo manual que eu fiz.

Se você é desse mercado e quer conversar, [me chama](mailto:igorcolombini@gmail.com).

---

## Autoria

Construído por [Igor Colombini](https://github.com/igorcolombini). 