import os
import logging
from extractor import IDMLExtractor

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

def main():
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    idml_file = os.path.join(root_dir, "data", "manual.idml")
    
    if not os.path.exists(idml_file):
        logging.error(f"Arquivo não encontrado: {idml_file}")
        return

    extractor = IDMLExtractor(idml_file)
    
    try:
        extractor.unzip()
        stories = extractor.get_story_files()
        
        if stories:
            # Chama o nosso novo motor de extração
            results = extractor.parse_and_filter(stories)
            logging.info("--- AMOSTRA DE TEXTOS LIMPOS ---")
            for i, text in enumerate(results["sample"]):
                logging.info(f"[{i}] {text}")
            logging.info("--------------------------------")
            
    finally:
        extractor.cleanup()

if __name__ == "__main__":
    main()