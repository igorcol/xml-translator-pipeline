import os, logging, argparse
from extractor import IDMLExtractor
from translator import OpenAITranslator
from builder import IDMLBuilder
from cache_manager import CacheManager

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

def setup_cli():
    parser = argparse.ArgumentParser(description="IDML Translator Pipeline")

    # --input - Caminho para o arquivo .idml 
    parser.add_argument("-i", "--input", default="data/manual.idml", help="Caminho para o arquivo .idml de origem")
    # --output - Caminho para salvar o arquivo traduzido (opcional)
    parser.add_argument("-o", "--output", required=False, help="Caminho para salvar o arquivo traduzido (opcional)")
    # --lang - Idioma alvo (ex: 'Espanhol', 'PT-BR')
    parser.add_argument("-l", "--lang", default="Português (Brasil)", help="Idioma alvo")

    # [ EM BREVE ]
    # --persona - Persona/Tom de voz para a IA
    parser.add_argument("-p", "--persona", default="Professor Maker", help="[EM BREVE...]")
    # --resume - Usa o cache local para retomar traduções paradas (Em breve)
    parser.add_argument("--resume", action="store_true", help="Usa o cache local para retomar traduções paradas (Em breve)")
    
    return parser.parse_args()

def main():
    args = setup_cli()
    idml_file = args.input
    output_file = args.output if args.output else f"{os.path.splitext(idml_file)[0]}_traduzido.idml"
    
    if not os.path.exists(idml_file):
        logging.error(f"Arquivo não encontrado: {idml_file}")
        return

    # Inicializa as Máquinas
    extractor = IDMLExtractor(idml_file)
    translator = OpenAITranslator(batch_size=50)
    cache = CacheManager() # Nosso novo Cofre
    
    try:
        extractor.unzip()
        stories = extractor.get_story_files()
        if not stories: return
        
        payload = extractor.build_memory_map(stories)
        
        # ==========================================
        # A TRIAGEM DE CACHE
        # ==========================================
        total_items = len(payload)
        final_translations = [None] * total_items # Array do tamanho exato do XML
        
        pending_texts = []
        pending_indices = []
        
        # Verifica o Cofre (cache)
        for i, item in enumerate(payload):
            original = item["original_text"]
            cached_translation = cache.get(original)
            
            if cached_translation:
                # Encontrou - Custo Zero.
                final_translations[i] = cached_translation
            else:
                # Inédito. Vai para o 'carrinho' da IA.
                pending_texts.append(original)
                pending_indices.append(i)
                
        logging.info(f"Triagem concluída: {total_items - len(pending_texts)} resgatados do cofre | {len(pending_texts)} enviados para IA.")

        # Processa apenas os inéditos na API
        if pending_texts:
            batches = translator.create_batches(pending_texts)
            logging.info(f"Iniciando tradução de {len(batches)} lotes inéditos...")
            
            processed_count = 0
            for i, batch in enumerate(batches):
                logging.info(f"Processando lote {i+1}/{len(batches)}...")
                translated_batch = translator.translate_batch(batch)
                
                # Guarda o resultado no cache e mapeia de volta na posição correta do XML
                for j, translated_text in enumerate(translated_batch):
                    original_idx = pending_indices[processed_count]
                    original_text = pending_texts[processed_count]
                    
                    final_translations[original_idx] = translated_text
                    cache.set(original_text, translated_text) 
                    
                    processed_count += 1
            
            # Salva o cache
            cache.save()
        else:
            logging.info("100% dos textos já estavam no cofre! Bypass total da API.")
            
        # ==========================================
        # RECONSTRUÇÃO
        # ==========================================
        builder = IDMLBuilder(extractor.temp_dir, extractor.xml_trees)
        builder.inject_translations(payload, final_translations)
        builder.save_xml_files()
        builder.repackage(output_file)
        
        logging.info(f"SUCESSO! Arquivo salvo em: {output_file}")
            
    except Exception as e:
        logging.error(f"O pipeline falhou: {e}")
        # Tenta salvar qualquer coisa que tenha processado antes de crashar
        cache.save() 
        
    finally:
        extractor.cleanup()

if __name__ == "__main__":
    main()