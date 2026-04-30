import os, logging, argparse, asyncio
from core.extractor import IDMLExtractor
from core.translator import OpenAITranslator
from core.builder import IDMLBuilder
from infra.cache_manager import CacheManager

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

def setup_cli():
    parser = argparse.ArgumentParser(description="IDML Translator Pipeline")

    parser.add_argument("-i", "--input", default="data/input/manual.idml", help="Caminho para o arquivo .idml de origem")
    parser.add_argument("-o", "--output", required=False, help="Caminho para salvar o arquivo traduzido (opcional)")
    parser.add_argument("-l", "--lang", default="Português (Brasil)", help="Idioma alvo")
    parser.add_argument("-p", "--persona", default="Professor Maker", help="[EM BREVE...]")
    parser.add_argument("--resume", action="store_true", help="Usa o cache local para retomar traduções paradas (Em breve)")

    return parser.parse_args()

async def main_async():
    args = setup_cli()
    idml_file = args.input

    if args.output:
        output_file = args.output
    else:
        base_name = os.path.basename(idml_file)
        name_only, ext = os.path.splitext(base_name)
        output_file = f"data/output/{name_only}_traduzido{ext}"

    if not os.path.exists(idml_file):
        logging.error(f"Arquivo não encontrado: {idml_file}")
        return

    extractor = IDMLExtractor(idml_file)
    translator = OpenAITranslator(batch_size=50, max_concurrency=5)
    cache = CacheManager() 

    try:
        extractor.unzip()
        stories = extractor.get_story_files()
        if not stories: return
        
        payload = extractor.build_memory_map(stories)
        total_items = len(payload)
        final_translations = [None] * total_items 
        
        pending_items = []
        pending_indices = []
        
        for i, item in enumerate(payload):
            original = item["original_text"]
            cached_translation = cache.get(original)
            
            if cached_translation:
                final_translations[i] = cached_translation
            else:
                pending_items.append(item)
                pending_indices.append(i)
                
        logging.info(f"Triagem: {total_items - len(pending_items)} no cofre | {len(pending_items)} para IA.")

        if pending_items:
            batches = translator.create_batches(pending_items)
            logging.info(f"Iniciando Motor Assíncrono para {len(batches)} lotes...")
            
            async def process_task(batch, chunk_items, chunk_indices, batch_idx):
                logging.info(f"-> Disparando Lote {batch_idx}")
                try:
                    translated_batch = await translator.translate_batch(batch)
                    
                    for j, translated_text in enumerate(translated_batch):
                        final_translations[chunk_indices[j]] = translated_text
                        
                        original_str = chunk_items[j]["original_text"]
                        cache.set(original_str, translated_text)
                    
                    cache.save()
                    logging.info(f"<- Lote {batch_idx} Retornou e foi salvo no cofre!")
                    return True
                except Exception as e:
                    logging.error(f"<- Lote {batch_idx} FALHOU fatalmente: {e}")
                    return False
            
            tasks = []
            for i, batch in enumerate(batches):
                start_ptr = i * translator.batch_size
                end_ptr = (i + 1) * translator.batch_size
                
                chunk_items = pending_items[start_ptr : end_ptr]
                chunk_indices = pending_indices[start_ptr : end_ptr]
                
                tasks.append(process_task(batch, chunk_items, chunk_indices, i+1))
                
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            if not all(results):
                logging.error("Um ou mais lotes falharam. O arquivo IDML não será gerado.")
                return
                
        builder = IDMLBuilder(extractor.temp_dir, extractor.xml_trees)
        builder.inject_translations(payload, final_translations)
        builder.save_xml_files()
        builder.repackage(output_file)
        
        logging.info(f"SUCESSO! Arquivo salvo em: {output_file}")

    except Exception as e:
        logging.error(f"O pipeline falhou: {e}")
    finally:
        cache.save()
        extractor.cleanup()

def main():
    asyncio.run(main_async())

if __name__ == "__main__":
    main()