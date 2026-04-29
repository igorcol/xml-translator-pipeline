import os
import logging
from extractor import IDMLExtractor
from translator import GeminiTranslator

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")


def main():
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    idml_file = os.path.join(root_dir, "data", "manual.idml")

    if not os.path.exists(idml_file):
        logging.error(f"Arquivo não encontrado: {idml_file}")
        return

    extractor = IDMLExtractor(idml_file)
    translator = GeminiTranslator(batch_size=5)  # Lote de 5 apenas para o teste

    try:
        extractor.unzip()
        stories = extractor.get_story_files()

        if stories:
            # 1. Extração
            payload = extractor.build_memory_map(stories)

            # Pegando apenas 5 itens de teste
            test_payload = payload[:5]
            text_only_batch = [item["original_text"] for item in test_payload]

            logging.info(f"Enviando lote de teste para a API...")
            logging.info(f"Original: {text_only_batch}")

            # 2. Tradução via IA
            translated_batch = translator.translate_batch(text_only_batch)

            logging.info(f"Tradução concluída!")
            logging.info(f"Retorno: {translated_batch}")

    finally:
        extractor.cleanup()


if __name__ == "__main__":
    main()
