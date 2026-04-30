import tempfile, shutil, logging, zipfile, os, re
from lxml import etree

# Configuração de log
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")


class IDMLExtractor:
    def __init__(self, idml_path: str):
        self.idml_path = idml_path
        # Diretório temporario
        self.temp_dir = tempfile.mkdtemp(prefix="idml_pipeline_")
        self.stories_dir = os.path.join(self.temp_dir, "Stories")
        # Dicionário para manter os arquivos XML abertos na memória
        self.xml_trees = {} 
        # Lista final para a IA
        self.translation_payload = []

    def unzip(self) -> str:
        """Descompacta o IDML no path temporário e retorna o caminho."""
        logging.info(f"Descompactando '{os.path.basename(self.idml_path)}'...")

        with zipfile.ZipFile(self.idml_path, "r") as zip_ref:
            zip_ref.extractall(self.temp_dir)

        logging.info(f"Descompactação concluída em: {self.temp_dir}")
        return self.temp_dir

    def get_story_files(self) -> list[str]:
        """Varre a pasta Stories e retorna a lista de arquivos XML que tenham texto."""
        if not os.path.exists(self.stories_dir):
            logging.error(
                "O arquivo não parece ser um IDML válido (Pasta 'Stories' ausente)."
            )
            return []

        # Filtra apenas XMLs que começam com Story_
        story_files = [
            os.path.join(self.stories_dir, f)
            for f in os.listdir(self.stories_dir)
            if f.startswith("Story_") and f.endswith(".xml")
        ]

        logging.info(
            f"{len(story_files)} arquivos Story encontrados para processamento."
        )
        return story_files

    # FUNÇÃO AUXILIAR DE CONTEXTUALIZAÇÃO
    def _get_paragraph_context(self, node) -> str:
        """
        Sobe na árvore até achar o ParagraphStyleRange e concatena
        .todo o texto legível daquele bloco para dar contexto à IA.
        """
        # Procura o ancestral que representa o parágrafo inteiro
        ancestors = node.xpath("ancestor::*[local-name()='ParagraphStyleRange']")
        
        if ancestors:
            # Pega o parágrafo
            paragraph_node = ancestors[-1]
            # Pega todos os nós de texto dentro deste parágrafo
            contents = paragraph_node.xpath(".//*[local-name()='Content']")
            # Concatena tudo mantendo os espaços originais para montar a frase
            full_text = "".join([c.text for c in contents if c.text])
            
            # Removem excesso de espaços apenas nas pontas
            return full_text.strip()
            
        # Fallback: Se o nó estiver solto sem parágrafo
        return node.text.strip() if node.text else ""

    def parse_and_filter(self, story_files: list[str]) -> dict:
        """
        Varre os XMLs, extrai e filtra os textos.
        Retorna um dicionário com estatísticas e uma amostra dos dados.
        """
        valid_texts = []
        bypass_count = 0

        logging.info("Iniciando varredura com lxml e XPath...")

        for file_path in story_files:
            tree = etree.parse(file_path)
            root = tree.getroot()

            contents = root.xpath("//*[local-name()='Content']")

            for content in contents:
                text = content.text
                if not text:
                    continue

                if re.search(r"[a-zA-Z]", text):
                    clean_text = text.strip()
                    valid_texts.append(clean_text)
                else:
                    bypass_count += 1

        logging.info(
            f"Filtro aplicado: {len(valid_texts)} segmentos válidos | {bypass_count} segmentos de lixo ignorados."
        )

        return {
            "valid_count": len(valid_texts),
            "bypass_count": bypass_count,
            "sample": valid_texts[:5], 
        }
    
    def build_memory_map(self, story_files: list[str]):
        """
        Carrega os XMLs na memória e mapeia os "nós" exatos que precisam de tradução.
        """
        bypass_count = 0
        
        for file_path in story_files:
            tree = etree.parse(file_path)
            self.xml_trees[file_path] = tree 
            
            contents = tree.xpath("//*[local-name()='Content']")
            
            for node in contents:
                text = node.text
                if not text:
                    continue
                
                if re.search(r'[a-zA-Z]', text):
                    clean_text = text.strip()
                    
                    # Chama a função de contexto
                    contexto_macro = self._get_paragraph_context(node)
                    
                    # O Payload agora é "tridimensional" (com contexto)
                    #! Mantem a chave "original_text" apenas por retrocompatibilidade rápida
                    #! com o CacheManager.
                    # Adiciona o "texto_alvo" e "contexto_macro"
                    self.translation_payload.append({
                        "node": node, 
                        "original_text": clean_text, # A chave de cache antiga
                        "texto_alvo": clean_text,    # O alvo real para a IA
                        "contexto_macro": contexto_macro # O contexto macro
                    })
                else:
                    bypass_count += 1
                    
        logging.info(f"Mapeamento concluído com Consciência de Contexto: {len(self.translation_payload)} segmentos | {bypass_count} ignorados.")
        return self.translation_payload

    def cleanup(self):
        """Apaga o path temporário."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
            logging.info("Diretório temporário limpo com sucesso.")