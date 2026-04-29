import os
import json
import logging
import asyncio
from openai import AsyncOpenAI
from dotenv import load_dotenv
from prompts import SYSTEM_INSTRUCTION

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

class OpenAITranslator:
    def __init__(self, batch_size=50, max_concurrency=5):
        load_dotenv()
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY não encontrada.")

        self.client = AsyncOpenAI(api_key=api_key)
        self.model = "gpt-4o-mini"
        self.batch_size = batch_size
        self.system_instruction = SYSTEM_INSTRUCTION
        self.semaphore = asyncio.Semaphore(max_concurrency)

    def create_batches(self, payload: list) -> list:
        return [payload[i : i + self.batch_size] for i in range(0, len(payload), self.batch_size)]

    async def _raw_translate(self, batch_texts: list[str]):
        """Apenas a chamada de rede protegida pelo semáforo."""
        prompt = f"Traduza este array JSON (Exatamente {len(batch_texts)} itens):\n{json.dumps(batch_texts, ensure_ascii=False)}"
        
        async with self.semaphore:
            response = await self.client.chat.completions.create(
                model=self.model,
                response_format={ "type": "json_object" },
                messages=[
                    {"role": "system", "content": self.system_instruction + "\n\nRetorne um objeto JSON: {'translations': [strings]}"},
                    {"role": "user", "content": prompt}
                ]
            )
            return json.loads(response.choices[0].message.content).get("translations", [])

    async def translate_batch(self, batch_texts: list[str], attempt=1) -> list[str]:
        """Lógica de retry e validação de contagem."""
        try:
            translated_array = await self._raw_translate(batch_texts)

            if len(translated_array) != len(batch_texts):
                raise ValueError(f"Dessincronização detectada: {len(batch_texts)} em | {len(translated_array)} out.")

            return translated_array

        except Exception as e:
            logging.error(f"Erro no Lote (Tentativa {attempt}): {e}")
            if attempt <= 3:
                wait = 2 ** attempt
                logging.info(f"Retentando lote em {wait}s...")
                await asyncio.sleep(wait)
                return await self.translate_batch(batch_texts, attempt + 1)
            else:
                logging.error("ERRO: Lote falhou após 3 tentativas...")
                raise e