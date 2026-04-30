import os, uuid, shutil, logging, asyncio
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse

# Importa Core e Infra
from core.extractor import IDMLExtractor
from core.translator import OpenAITranslator
from core.builder import IDMLBuilder
from infra.cache_manager import CacheManager

# ==========================
DEBUG_MODE = True  # Deixar False em Produção para ativar a autolimpeza
# ==========================

router = APIRouter(
    prefix="/api/v1",
    tags=["Tradução"]
)


# * Limpar arquivos temporarios gerados pela API
def cleanup_temp_files(input_path: str, output_path: str):
    if DEBUG_MODE:
        logging.info("🧹 [CLEANUP IGNORADO] DEBUG_MODE está Ativado. Os arquivos foram mantidos no servidor para inspeção.")
        return
    try:
        if os.path.exists(input_path):
            os.remove(input_path)
        if os.path.exists(output_path):
            os.remove(output_path)
        logging.info("🧹 [CLEANUP CONCLUÍDO] Arquivos temporários foram apagados do servidor.")
    except Exception as e:
        logging.error(f"Erro ao tentar limpar arquivos residuais: {e}")


#* ====== /TRANSLATE ======
@router.post("/translate", response_class=FileResponse)
async def translate_idml(
    background_tasks: BackgroundTasks,
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
        pending_items, pending_indices = [], []
        
        # Triagem de Cache
        for i, item in enumerate(payload):
            original = item["original_text"]
            cached = cache.get(original)
            if cached:
                final_translations[i] = cached
            else:
                pending_items.append(item)
                pending_indices.append(i)
                
        logging.info(f"Motor -> Triagem: {len(payload)-len(pending_items)} no cofre | {len(pending_items)} para IA.")

        # Processamento Assíncrono com OpenAI
        if pending_items:
            batches = translator.create_batches(pending_items)
            
            async def process_task(batch, chunk_items, chunk_indices, batch_idx):
                try:
                    translated_batch = await translator.translate_batch(batch)
                    for j, translated_text in enumerate(translated_batch):
                        final_translations[chunk_indices[j]] = translated_text
                        
                        # Cache cfeito APENAS pelo texto original
                        cache.set(chunk_items[j]["original_text"], translated_text)
                    
                    # Salva o cache após cada lote processado
                    cache.save()
                    return True
                except Exception as e:
                    logging.error(f"Lote {batch_idx} falhou: {e}")
                    return False
            
            tasks = []
            for i, batch in enumerate(batches):
                start_idx = i * translator.batch_size
                end_idx = (i + 1) * translator.batch_size
                
                chunk_items = pending_items[start_idx : end_idx]
                chunk_indices = pending_indices[start_idx : end_idx]
                
                tasks.append(process_task(batch, chunk_items, chunk_indices, i + 1))
                
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

    # Task de cleanup para rodar DEPOIS que o usuário baixar o arquivo gerado
    background_tasks.add_task(cleanup_temp_files, input_path, output_path)

    # Retorna o arquivo como um Download
    return FileResponse(
        path=output_path,
        filename=f"Traduzido_{file.filename}",
        media_type="application/octet-stream" # Força o navegador a baixar
    )