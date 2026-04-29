from pydantic import BaseModel

class TranslationResponse(BaseModel):
    """Contrato de resposta quando a tradução for enfileirada ou concluída."""
    status: str
    message: str
    filename: str