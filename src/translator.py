import os, time, json, logging, google.generativeai as genai
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

        # Persona da IA
        self.system_instruction = SYSTEM_INSTRUCTION

        def create_batches(self, payload: list) -> list:
            """Separa a lista inteira em lotes menores baseados no batch_size."""
            return [
                payload[i : i + self.batch_size]
                for i in range(0, len(payload), self.batch_size)
            ]

        def translate_batch(self, batch_texts: list[str], attempt=1) -> list[str]:
            """
            Envia um batch para a API forçando a saída em JSON.
            Inclui retentativa automática em caso de falha.
            """
            prompt = f"""
            {self.system_instruction}
            
            Traduza o seguinte array JSON de textos do Inglês para o Português (Brasil) de acordo com a sua persona dada.
            MANTENHA EXATAMENTE o mesmo número de itens no array de resposta.
            Retorne APENAS um array JSON válido, sem formatação markdown (sem ```json), apenas o array puro:
            
            {json.dumps(batch_texts, ensure_ascii=False)}
            """

            try:
                response = self.model.generate_content(prompt)
                # Limpeza rapido caso IA mande blocos md
                clean_response = (
                    response.text.replace("```json", "").replace("```", "").strip()
                )
                translated_array = json.loads(clean_response)

                # Validação de segurança
                if len(translated_array) != len(batch_texts):
                    raise ValueError(
                        f"Dessincronização: {len(batch_texts)} itens enviados | {len(translated_array)} devolvidos pela IA."
                    )

                return translated_array

            except Exception as e:
                logging.error(f"Falha no lote (Tentativa {attempt}): {e}")
                if attempt <= 3:
                    sleep_time = 2**attempt  # 2s, 4s, 8s...
                    logging.info(f"Retentando em {sleep_time} segundos...")
                    time.sleep(sleep_time)
                    return self.translate_batch(batch_texts, attempt + 1)
                else:
                    logging.error("Lote falhou após 3 tentativas. Abortando operação.")
                    raise e
