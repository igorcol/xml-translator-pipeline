# ⚙️ IDML Translation Pipeline

> **De 5 horas de cliques manuais para 5 minutos de execução.** > Um pipeline de automação construído em Python que aplica engenharia reversa em arquivos do Adobe InDesign (.idml) e orquestra a API do Gemini para traduções em massa, com zero perda de layout.

## ⚠️ O Problema

Durante um projeto de tradução técnica freelance (um manual do inglês para o português), me deparei com documentos de 1600 linhas. O fluxo normal exigia abrir o arquivo em um software CAT (OmegaT) e usar macros (AutoHotKey) para copiar e colar trechos traduzidos pelo LLM, linha por linha.

**Conclusão:** Demora excessiva, gasto desnecessário de tempo e alta margem para erro humano.

## 🚀 A Solução

Desenvolvi um script de processamento local que ignora totalmente a interface gráfica. O script abre o `.idml`, filtra o poluição visual, orquestra a tradução com IA em lotes paralelos e reconstrói o arquivo original intacto. 

**Os 3 Pilares da Arquitetura:**
1. **Automação:** O processo manual foi aniquilado. Input de arquivo -> output de arquivo.
2. **LLM Orchestration:** Uso cirúrgico da IA (Gemini 2.5 Flash) focada na tradução contextual (Persona de um "Professor Maker" para garantir precisão técnica no assunto), forçando saídas em JSON estrito (MIME type override).
3. **Engenharia de Dados (Bypass de UI):** Operação direta nos arquivos XML compactados. 

## 🧠 Destaques Técnicos

O maior desafio de traduzir um IDML programaticamente não é a tradução, é a **preservação do layout**. O InDesign gera centenas de tags XML inúteis, espaços em branco para alinhamento e separadores visuais. Se enviados para a IA, esses elementos quebram o retorno e consomem tokens desnecessários.

Por isso Criei um ***Sistema de Indexação por Bypass***. 
O extrator (`lxml`) varre as tags e usa expressões regulares (`Regex`) para identificar o que é texto real e o que é "lixo de layout". O 'ruído' fica salvo em um dicionário de estado na memória local, e apenas o texto útil é empacotado e enviado à API. Na volta, o script cruza o array traduzido com a memória, remontando o XML e garantindo que o designer que abrir o arquivo final não encontre uma vírgula fora do lugar.

## 🛠️ Como usar

1. Clone o repositório e acesse a pasta do projeto.

2. Crie e ative seu ambiente virtual:
   ```bash
   python -m venv venv
   source venv/bin/activate  # No Windows: .\venv\Scripts\activate
    ```
3. Instale as dependências:
    ```bash
    pip install -r requirements.txt
    ```
4. Crie um arquivo .env na raiz e insira sua chave do Google Studio:
    ```bash
    GEMINI_API_KEY=sua_chave_aqui
    ```
5. Coloque seu arquivo na pasta /data renomeado para manual.idml e rode a máquina:
    ```bash
    python src/main.py
    ```

## Roadmap e Próximos Passos
Este script nasceu como um utilitário para resolver uma dor pessoal, mas a arquitetura foi desenhada pensando em escalabilidade. Os próximos passos incluem:

- [ ] Web Dashboard: Envolver o script Python com um frontend moderno, permitindo upload via drag-and-drop, monitoramento em tempo real e exibição da tradução.

- [ ] Suporte Multilíngue: Adicionar passagem de parâmetros via CLI para seleção dinâmica de idioma alvo e persona da IA.


