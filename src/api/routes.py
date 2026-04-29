from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from api.schemas import TranslationResponse
import logging

# Inicializa o roteador para o endpoint de tradução
router = APIRouter(
    prefix="/api/v1",
    tags=["Tradução"]
)

@router.post("/translate", response_model=TranslationResponse)
async def translate_idml(
    file: UploadFile = File(..., description="O arquivo .idml originalpara tradução."),
    target_lang: str = Form("Português (Brasil)", description="O idioma alvo da tradução.")
):
    """
    Recebe um arquivo .idml, valida sua extensão e inicia o pipeline de tradução.
    """
    logging.info(f"Recebendo requisição de tradução para o arquivo: {file.filename} (Idioma: {target_lang})")

    # Validação
    if not file.filename.lower().endswith(".idml"):
        logging.warning(f"Tentativa de upload de arquivo inválido: {file.filename}")
        raise HTTPException(
            status_code=400,
            detail="Formato de arquivo inválido. Apenas arquivos .idml são aceitos."
        )
    
    # ==========================================
    # O MOTOR VAI ENTRAR AQUI NA FASE 3
    # Por enquanto, vamos apenas fingir que recebemos e validamos para testar a rota.
    # ==========================================

    return TranslationResponse(
        status="success",
        message="Arquivo recebido e validado com sucesso!",
        filename=file.filename
    )
