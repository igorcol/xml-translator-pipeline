import os
import time
import json
import logging
import google.generativeai as genai
from dotenv import load_dotenv
from prompts import SYSTEM_INSTRUCTION

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

class GeminiTranslator:
    def __init__(self, batch_size=50):
        load_dotenv()
        api_key = os.getenv("GEMINI_API_KEY")

        if not api_key:
            raise ValueError("GEMINI_API_KEY Não encontrada no arquivo .env")

        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel("gemini-2.5-flash")
        self.batch_size = batch_size
        self.system_instruction = SYSTEM_INSTRUCTION

    def create_batches(self, payload: list) -> list:
        return [
            payload[i : i + self.batch_size]
            for i in range(0, len(payload), self.batch_size)
        ]

    def translate_batch(self, batch_texts: list[str], attempt=1) -> list[str]:
        prompt = f"""
        {self.system_instruction}
        
        Traduza o seguinte array de textos do Inglês para o Português (Brasil) de acordo com a sua persona dada.
        MANTENHA EXATAMENTE o mesmo número de itens no array de resposta.
        
        {json.dumps(batch_texts, ensure_ascii=False)}
        """

        try:
            # Força o MIME Type para JSON puro na SDK.
            # impede que a IA escreva texto fora do array ou quebre aspas.
            response = self.model.generate_content(
                prompt,
                generation_config={"response_mime_type": "application/json"}
            )
            
            translated_array = json.loads(response.text)

            # Validação de segurança
            if len(translated_array) != len(batch_texts):
                raise ValueError(
                    f"Dessincronização: {len(batch_texts)} itens enviados | {len(translated_array)} devolvidos."
                )

            # Sleep para não estourar os 15 RPM do plano gratuito
            time.sleep(4) 
            return translated_array

        except Exception as e:
            error_msg = str(e)
            logging.error(f"Falha no lote (Tentativa {attempt}): {error_msg}")
            
            if attempt <= 3:
                # Tratamento de precisão para Rate Limit (Erro 429)
                if "429" in error_msg or "Quota" in error_msg:
                    sleep_time = 62 # O Google pede 56s
                    logging.warning(f"Limite do Free Tier atingido. Resfriando o motor por {sleep_time} segundos...")
                else:
                    sleep_time = 2 ** attempt
                    logging.info(f"Retentando em {sleep_time} segundos...")
                    
                time.sleep(sleep_time)
                return self.translate_batch(batch_texts, attempt + 1)
            else:
                logging.error("Lote falhou após 3 tentativas. Abortando operação.")
                raise e