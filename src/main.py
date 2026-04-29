import os, logging, argparse, asyncio
from extractor import IDMLExtractor
from translator import OpenAITranslator
from builder import IDMLBuilder
from cache_manager import CacheManager

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")


def setup_cli():
    parser = argparse.ArgumentParser(description="IDML Translator Pipeline")

    # --input - Caminho para o arquivo .idml
    parser.add_argument(
        "-i",
        "--input",
        default="data/manual.idml",
        help="Caminho para o arquivo .idml de origem",
    )
    # --output - Caminho para salvar o arquivo traduzido (opcional)
    parser.add_argument(
        "-o",
        "--output",
        required=False,
        help="Caminho para salvar o arquivo traduzido (opcional)",
    )
    # --lang - Idioma alvo (ex: 'Espanhol', 'PT-BR')
    parser.add_argument(
        "-l", "--lang", default="Português (Brasil)", help="Idioma alvo"
    )

    # [ EM BREVE ] --persona - Persona/Tom de voz para a IA
    parser.add_argument(
        "-p", "--persona", default="Professor Maker", help="[EM BREVE...]"
    )
    # [ EM BREVE ] --resume - Usa o cache local para retomar traduções paradas (Em breve)
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Usa o cache local para retomar traduções paradas (Em breve)",
    )

    return parser.parse_args()


async def main_async():
    args = setup_cli()
    idml_file = args.input
    output_file = (
        args.output
        if args.output
        else f"{os.path.splitext(idml_file)[0]}_traduzido.idml"
    )

    if not os.path.exists(idml_file):
        logging.error(f"Arquivo não encontrado: {idml_file}")
        return

    # Inicializa as Classes
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
        
        pending_texts = []
        pending_indices = []
        
        for i, item in enumerate(payload):
            original = item["original_text"]
            cached_translation = cache.get(original)
            
            if cached_translation:
                final_translations[i] = cached_translation
            else:
                pending_texts.append(original)
                pending_indices.append(i)
                
        logging.info(f"Triagem: {total_items - len(pending_texts)} no cofre | {len(pending_texts)} para IA.")

        if pending_texts:
            batches = translator.create_batches(pending_texts)
            logging.info(f"Iniciando Motor Assíncrono para {len(batches)} lotes...")
            
            # Cria a lista de promessas (tasks)
            async def process_task(batch, chunk_texts, chunk_indices, batch_idx):
                logging.info(f"-> Disparando Lote {batch_idx}")
                translated_batch = await translator.translate_batch(batch)
                logging.info(f"<- Lote {batch_idx} Retornou!")
                return translated_batch, chunk_texts, chunk_indices
            
            tasks = []
            for i, batch in enumerate(batches):
                # Recorta os textos e os indices originais referentes a este batch
                chunk_texts = pending_texts[i*translator.batch_size : (i+1)*translator.batch_size]
                chunk_indices = pending_indices[i*translator.batch_size : (i+1)*translator.batch_size]
                tasks.append(process_task(batch, chunk_texts, chunk_indices, i+1))
                
            # O as_completed processa as promessas na ordem em que terminam
            for task in asyncio.as_completed(tasks):
                translated_batch, chunk_texts, chunk_indices = await task
                
                # Injeta de volta na posição exata
                for j, translated_text in enumerate(translated_batch):
                    final_translations[chunk_indices[j]] = translated_text
                    cache.set(chunk_texts[j], translated_text)
                    
                cache.save() # Salva a cada lote que volta
                
        # Reconstrução
        builder = IDMLBuilder(extractor.temp_dir, extractor.xml_trees)
        builder.inject_translations(payload, final_translations)
        builder.save_xml_files()
        builder.repackage(output_file)
        
        logging.info(f"SUCESSO ABSOLUTO! Arquivo salvo em: {output_file}")

    except Exception as e:
        logging.error(f"O pipeline falhou: {e}")
    except KeyboardInterrupt:
        logging.warning(
            "\nProcesso interrompido pelo usuário (Ctrl+C). Fechando o cofre com segurança..."
        )
    finally:
        cache.save()
        extractor.cleanup()


def main():
    asyncio.run(main_async())

if __name__ == "__main__":
    main()
