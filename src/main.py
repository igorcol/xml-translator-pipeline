import os
import logging
from extractor import IDMLExtractor
from translator import OpenAITranslator
from builder import IDMLBuilder

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')


def main():
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    idml_file = os.path.join(root_dir, "data", "manual.idml")
    output_file = os.path.join(root_dir, "data", "manual_pt.idml")

    if not  os.path.exists(idml_file):
        logging.error(f"Arquivo não encontraro: {idml_file}")
        return
    
    extractor = IDMLExtractor(idml_file)
    translator = OpenAITranslator(batch_size=50)

    try:
        # Extração
        extractor.unzip()
        stories = extractor.get_story_files()

        if not stories:
            logging.error("Nenhuam story encontrada.")
            return
        
        payload = extractor.build_memory_map(stories)

        # Preparação de Lotes
        text_only_list = [item["original_text"] for item in payload]
        batches = translator.create_batches(text_only_list)
        all_translations = []

        # Processamento na IA
        logging.info(f"Iniciação tradução em massa de {len(batches)} lotes...")
        for i, batch in enumerate(batches):
            logging.info(f"Processando lote {i+1}/{len(batches)}...")
            translated_batch = translator.translate_batch(batch)
            all_translations.extend(translated_batch)

        # Reconstrução do IDML
        builder = IDMLBuilder(extractor.temp_dir, extractor.xml_trees)
        builder.inject_translation(payload, all_translations)
        builder.save_xml_files()
        builder.repackage()

        logging.info(f"SUCESSO!! O manual traduzido está em: {output_file}")

    except Exception as e:
        logging.error(f"O pipeline falhou: {e}")
        
    finally:
        extractor.cleanup()

if __name__ == "__main__":
    main()