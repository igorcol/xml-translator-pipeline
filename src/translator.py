import os
import time
import json
import logging
from openai import OpenAI
from dotenv import load_dotenv
from prompts import SYSTEM_INSTRUCTION

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

class OpenAITranslator:
    def __init__(self, batch_size=50):
        load_dotenv()
        api_key = os.getenv("OPENAI_API_KEY")

        if not api_key:
            raise ValueError("OPENAI_API_KEY Não encontrada no arquivo .env")

        # Inicializa OpenAI
        self.client = OpenAI(api_key=api_key)
        self.model = "gpt-4o-mini"
        self.batch_size = batch_size
        self.system_instruction = SYSTEM_INSTRUCTION

    def create_batches(self, payload: list) -> list:
        return [
            payload[i : i + self.batch_size]
            for i in range(0, len(payload), self.batch_size)
        ]

    def translate_batch(self, batch_texts: list[str], attempt=1) -> list[str]:
        prompt = f"""
        Traduza o seguinte array de textos do Inglês para o Português (Brasil).
        MANTENHA EXATAMENTE o mesmo número de itens.
        
        {json.dumps(batch_texts, ensure_ascii=False)}
        """

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                response_format={ "type": "json_object" },
                messages=[
                    {"role": "system", "content": self.system_instruction + "\n\nRETORNE UM OBJETO JSON VÁLIDO COM UMA ÚNICA CHAVE CHAMADA 'translations' QUE CONTÉM O ARRAY DE STRINGS TRADUZIDAS."},
                    {"role": "user", "content": prompt}
                ]
            )
            
            # Acessa texto da resposta e faz o parse do JSON
            response_content = json.loads(response.choices[0].message.content)
            translated_array = response_content.get("translations", [])

            # Segurança estrutural
            if len(translated_array) != len(batch_texts):
                raise ValueError(
                    f"Dessincronização: {len(batch_texts)} itens enviados | {len(translated_array)} devolvidos."
                )

            return translated_array

        except Exception as e:
            logging.error(f"Falha no lote (Tentativa {attempt}): {str(e)}")
            
            if attempt <= 3:
                sleep_time = 2 ** attempt
                logging.info(f"Retentando em {sleep_time} segundos...")
                time.sleep(sleep_time)
                return self.translate_batch(batch_texts, attempt + 1)
            else:
                logging.error("Lote falhou após 3 tentativas. Abortando operação.")
                raise e