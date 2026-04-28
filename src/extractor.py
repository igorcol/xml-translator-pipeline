import tempfile, shutil, logging, zipfile, os, re
from lxml import etree

# * Abre o arquivo IDML e pega os XMLs.

# Configuração de log
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")


class IDMLExtractor:
    def __init__(self, idml_path: str):
        self.idml_path = idml_path
        # Diretório temporario seguro
        self.temp_dir = tempfile.mkdtemp(prefix="idml_pipeline_")
        self.stories_dir = os.path.join(self.temp_dir, "Stories")
        # Dicionário para manter os arquivos XML abertos na memória
        self.xml_trees = {} 
        # Lista final que vai para o Gemini
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

            # XPath "//*[local-name()='Content']" ignora os namespaces da Adobe
            # acha todas as tags <Content>
            contents = root.xpath("//*[local-name()='Content']")

            for content in contents:
                text = content.text
                if not text:
                    continue

                # Deve que ter pelo menos uma letra (a-z, A-Z)
                # Sendo só número traços (------) ou ícones (▶) Regex ignora.
                if re.search(r"[a-zA-Z]", text):
                    # Remove os espaços grandes no texto
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
            "sample": valid_texts[:5],  # Pega os 5 primeiros para validarmos
        }
    
    def build_memory_map(self, story_files: list[str]):
        """
        Carrega os XMLs na memória e mapeia os "nós" exatos que precisam de tradução.
        """
        bypass_count = 0
        
        for file_path in story_files:
            tree = etree.parse(file_path)
            # Salva a árvore XML na memória para sobrescrever
            self.xml_trees[file_path] = tree 
            
            contents = tree.xpath("//*[local-name()='Content']")
            
            for node in contents:
                text = node.text
                if not text:
                    continue
                
                if re.search(r'[a-zA-Z]', text):
                    clean_text = text.strip()
                    # Guarda o nó original e o texto
                    self.translation_payload.append({
                        "node": node, 
                        "original_text": clean_text
                    })
                else:
                    bypass_count += 1
                    
        logging.info(f"Mapeamento concluído: {len(self.translation_payload)} segmentos atrelados aos nós XML | {bypass_count} ignorados.")
        return self.translation_payload

    def cleanup(self):
        """Apaga o path temporário."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
            logging.info("Diretório temporário limpo com sucesso.")
