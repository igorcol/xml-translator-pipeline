import os, uuid, shutil, logging, asyncio
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse

# Importa Core e Infra
from core.extractor import IDMLExtractor
from core.translator import OpenAITranslator
from core.builder import IDMLBuilder
from infra.cache_manager import CacheManager

router = APIRouter(
    prefix="/api/v1",
    tags=["Tradução"]
)

@router.post("/translate", response_class=FileResponse)
async def translate_idml(
    file: UploadFile = File(..., description="O arquivo .idml original"),
    target_lang: str = Form("Português (Brasil)", description="O idioma alvo")
):
    logging.info(f"Recebendo arquivo: {file.filename} (Idioma: {target_lang})")

    if not file.filename.lower().endswith(".idml"):
        raise HTTPException(status_code=400, detail="Formato inválido. Envie um .idml")

    # Gera um ID único para esta requisição
    request_id = uuid.uuid4().hex[:8]
    input_path = f"data/input/{request_id}_{file.filename}"
    output_path = f"data/output/{request_id}_traduzido_{file.filename}"

    os.makedirs("data/input", exist_ok=True)
    os.makedirs("data/output", exist_ok=True)

    # Salva o arquivo da memória da web direto no SSD
    with open(input_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    logging.info(f"Arquivo físico salvo em: {input_path}. Ligando o motor...")

    extractor = IDMLExtractor(input_path)
    translator = OpenAITranslator(batch_size=50, max_concurrency=5)
    cache = CacheManager()

    try:
        # Extração
        extractor.unzip()
        stories = extractor.get_story_files()
        if not stories:
            raise HTTPException(status_code=500, detail="Nenhum texto encontrado no IDML.")
        
        payload = extractor.build_memory_map(stories)
        final_translations = [None] * len(payload)
        pending_texts, pending_indices = [], []
        
        # Triagem de Cache
        for i, item in enumerate(payload):
            original = item["original_text"]
            cached = cache.get(original)
            if cached:
                final_translations[i] = cached
            else:
                pending_texts.append(original)
                pending_indices.append(i)
                
        logging.info(f"Motor -> Triagem: {len(payload)-len(pending_texts)} no cofre | {len(pending_texts)} para IA.")

        # Processamento Assíncrono com a OpenAI
        if pending_texts:
            batches = translator.create_batches(pending_texts)
            
            async def process_task(batch, chunk_texts, chunk_indices, batch_idx):
                try:
                    translated_batch = await translator.translate_batch(batch)
                    for j, translated_text in enumerate(translated_batch):
                        final_translations[chunk_indices[j]] = translated_text
                        cache.set(chunk_texts[j], translated_text)
                    cache.save()
                    return True
                except Exception as e:
                    logging.error(f"Lote {batch_idx} falhou: {e}")
                    return False
            
            tasks = []
            for i, batch in enumerate(batches):
                chunk_texts = pending_texts[i*translator.batch_size : (i+1)*translator.batch_size]
                chunk_indices = pending_indices[i*translator.batch_size : (i+1)*translator.batch_size]
                tasks.append(process_task(batch, chunk_texts, chunk_indices, i+1))
                
            results = await asyncio.gather(*tasks, return_exceptions=True)
            if not all(results):
                raise HTTPException(status_code=500, detail="Falha de comunicação com a IA durante a tradução.")

        # Reconstrução do IDML
        builder = IDMLBuilder(extractor.temp_dir, extractor.xml_trees)
        builder.inject_translations(payload, final_translations)
        builder.save_xml_files()
        builder.repackage(output_path)
        logging.info(f"Reconstrução concluída. Devolvendo para o usuário!")

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Erro fatal no pipeline: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cache.save()
        extractor.cleanup()

    # Retorna o arquivo como um Download
    return FileResponse(
        path=output_path,
        filename=f"Traduzido_{file.filename}",
        media_type="application/octet-stream" # Força o navegador a baixar
    )