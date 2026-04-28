import os
import logging
from extractor import IDMLExtractor

# Padrão de logs
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

def main():
    # Caminho dinâmico para garantir que funcione independente de onde o terminal for aberto
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    idml_file = os.path.join(root_dir, "data", "manual.idml")
    
    if not os.path.exists(idml_file):
        logging.error(f"Arquivo não encontrado: {idml_file}")
        logging.error("Certifique-se de que o arquivo se chama 'manual.idml' e está na pasta 'data/'")
        return

    # Instancia classe do extractor.py
    extractor = IDMLExtractor(idml_file)
    
    try:
        # Descompacta na memória
        extractor.unzip()
        # Varre os XMLs
        stories = extractor.get_story_files()
        
        if stories:
            logging.info(f"Sucesso! Motor engatado. Exemplo do primeiro arquivo encontrado: {os.path.basename(stories[0])}")
        else:
            logging.warning("Nenhum arquivo Story_*.xml encontrado.")
            
    finally:
        # Limpa a pasta temporária
        extractor.cleanup()

if __name__ == "__main__":
    main()