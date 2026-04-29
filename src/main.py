import os, logging, argparse
from extractor import IDMLExtractor
from translator import OpenAITranslator
from builder import IDMLBuilder

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

def setup_cli():
    parser = argparse.ArgumentParser(description="IDML Translator Pipeline - Bypass nativo de UI para localização de arquivos.")

    # --input - Caminho para o arquivo .idml 
    parser.add_argument("-i", "--input", default="data/manual.idml", help="Caminho para o arquivo .idml de origem")
    # --output - Caminho para salvar o arquivo traduzido (opcional)
    parser.add_argument("-o", "--output", required=False, help="Caminho para salvar o arquivo traduzido (opcional)")
    # --lang - Idioma alvo (ex: 'Espanhol', 'PT-BR')
    parser.add_argument("-l", "--lang", default="Português (Brasil)", help="[EM BREVE...]")
    # --persona - Persona/Tom de voz para a IA
    parser.add_argument("-p", "--persona", default="Professor Maker", help="[EM BREVE...]")
    # --resume - Usa o cache local para retomar traduções paradas (Em breve)
    parser.add_argument("--resume", action="store_true", help="Usa o cache local para retomar traduções paradas (Em breve)")
    
    return parser.parse_args()

def main():
    args = setup_cli()

    idml_file = args.input
    # Se não passar input, gera automaticamente um nome 'arquivo_traduzido.idml'
    if args.output:
        output_file = args.output
    else:
        base_name, ext = os.path.splitext(idml_file)
        output_file = f"{base_name}_traduzido{ext}"

    if not os.path.exists(idml_file):
        logging.error(f"Arquivo não encontrado: {idml_file}")
        return
    
    
    extractor = IDMLExtractor(idml_file)
    # TODO: No futuro, passar args.lang e args.persona para o Translator
    translator = OpenAITranslator(batch_size=50)

    try:
        # Extração
        extractor.unzip()
        stories = extractor.get_story_files()

        if not stories:
            logging.error("Nenhuma story encontrada no IDML.")
            return
        
        payload = extractor.build_memory_map(stories)

        # Preparação de Lotes
        text_only_list = [item["original_text"] for item in payload]
        batches = translator.create_batches(text_only_list)
        all_translations = []

        # -- Processamento na IA
        logging.info(f"Alvo: {args.lang} | Persona: {args.persona}")
        logging.info(f"Iniciando tradução de {len(batches)} lotes...")

        for i, batch in enumerate(batches):
            logging.info(f"Processando lote {i+1}/{len(batches)}...")
            # TODO: Simulando o loop para não gastar API até o cache estar pronto
            translated_batch = [f"[SIMULADO] {texto}" for texto in batch]
            # translated_batch = translator.translate_batch(batch) 
            all_translations.extend(translated_batch)

        # -- Reconstrução do IDML
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