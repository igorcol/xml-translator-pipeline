import tempfile, shutil, logging, zipfile, os

# * Abre o arquivo IDML e pega os XMLs.

# Configuração de log
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

class IDMLExtractor:
    def __init__(self, idml_path: str):
        self.idml_path = idml_path
        # Diretório temporario seguro
        self.temp_dir = tempfile.mkdtemp(prefix="idml_pipeline_")
        self.stories_dir = os.path.join(self.temp_dir, 'Stories')

    def unzip(self) -> str:
        """Descompacta o IDML no path temporário e retorna o caminho."""
        logging.info(f"Descompactando '{os.path.basename(self.idml_path)}'...")

        with zipfile.ZipFile(self.idml_path, 'r') as zip_ref:
            zip_ref.extractall(self.temp_dir)

        logging.info(f"Descompactação concluída em: {self.temp_dir}")
        return self.temp_dir
    
    def get_story_files(self) -> list[str]:
        """Varre a pasta Stories e retorna a lista de arquivos XML que tenham texto."""
        if not os.path.exists(self.stories_dir):
            logging.error("O arquivo não parece ser um IDML válido (Pasta 'Stories' ausente).")
            return []
        
        #Filtra apenas XMLs que começam com Story_
        story_files = [
            os.path.join(self.stories_dir, f)
            for f in os.listdir(self.stories_dir)
            if f.startswith('Story_') and f.endswith('.xml')
        ]

        logging.info(f"{len(story_files)} arquivos Story encontrados para processamento.")
        return story_files
    
    def cleanup(self):
        """Apaga o path temporário."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
            logging.info("Diretório temporário limpo com sucesso.")