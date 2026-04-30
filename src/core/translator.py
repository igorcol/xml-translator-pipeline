import os, json, logging, asyncio, re
from openai import AsyncOpenAI
from dotenv import load_dotenv
from config.prompts import SYSTEM_INSTRUCTION

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
        return [
            payload[i : i + self.batch_size]
            for i in range(0, len(payload), self.batch_size)
        ]

    async def _raw_translate(self, batch_payloads: list[dict]):

        # Filtra o dicionário para a IA não receber objeto _Element
        prompt_data = {
            "itens_para_traduzir": [
                {
                    "id": i,
                    "texto_alvo": item["texto_alvo"],
                    "contexto_macro": item["contexto_macro"],
                }
                for i, item in enumerate(batch_payloads)
            ]
        }

        prompt = f"Traduza este lote (Exatamente {len(batch_payloads)} itens):\n{json.dumps(prompt_data, ensure_ascii=False)}"

        async with self.semaphore:
            response = await self.client.chat.completions.create(
                model=self.model,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": self.system_instruction},
                    {"role": "user", "content": prompt},
                ],
            )
            return json.loads(response.choices[0].message.content).get(
                "translations", []
            )

    async def translate_batch(self, batch_payloads: list[dict], attempt=1) -> list[str]:
        try:
            # translated_objects é uma lista de dicts com 'id' e 'traducao'
            translated_objects = await self._raw_translate(batch_payloads)

            # Reconstrução Segura Mapeia o resultado pelo ID que a IA devolveu
            result_map = {
                item["id"]: item["traducao"]
                for item in translated_objects
                if isinstance(item, dict) and "id" in item and "traducao" in item
            }

            # Validação - A IA devolve o número exato de IDs solicitados?
            if len(result_map) != len(batch_payloads):
                debug_data = {
                    "input_lenght": len(batch_payloads),
                    "output_lenght": len(result_map),
                    "input_texts": [
                        {"id": i, "alvo": item["texto_alvo"]}
                        for i, item in enumerate(batch_payloads)
                    ],
                    "output_textts": translated_objects,
                }
                debug_file = "data/output/debug_desync.json"
                os.makedirs(os.path.dirname(debug_file), exist_ok=True)
                with open(debug_file, "w", encoding="UTF-8") as f:
                    json.dump(debug_data, f, ensure_ascii=False, indent=2)

                raise ValueError(
                    f"Dessincronização de IDs detectada: {len(batch_payloads)} in | {len(result_map)} out."
                )

            # Monta o array final de strings na ordem EXATA do lote original
            translated_array = [result_map[i] for i in range(len(batch_payloads))]
            return translated_array

        except Exception as e:
            logging.error(f"Erro no Lote (Tentativa {attempt}): {e}")

            if attempt <= 3:
                wait = 2**attempt
                logging.info(f"Retentando lote em {wait}s...")
                await asyncio.sleep(wait)
                return await self.translate_batch(batch_payloads, attempt + 1)
            else:
                logging.warning("⚠️ Ativando Modo Sniper (1-por-1) higienizado...")
                sniper_results = []
                for item in batch_payloads:
                    texto = item["texto_alvo"]

                    if not texto.strip() or not re.search(r"[a-zA-Z]", texto):
                        sniper_results.append(texto)
                        continue

                    try:
                        # O raw_translate recebe um array de 1 item, a IA devolve ID 0
                        res_objs = await self._raw_translate([item])
                        traducao_sniper = res_objs[0].get("traducao", texto)
                        sniper_results.append(traducao_sniper)
                    except:
                        sniper_results.append(texto)
                return sniper_results
