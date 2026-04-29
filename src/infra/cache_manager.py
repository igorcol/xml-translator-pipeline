import os, json, logging

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

class CacheManager:
    def __init__(self, cache_file="data/cache/translation_cache.json"):
        self.cache_file = cache_file
        self.cache = self._load_cache()

    def _load_cache(self) -> dict:
        """Carrega o cofre para a memória. Se não existir, cria um vazio."""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    logging.info(f"Cofre carregado com {len(data)} traduções salvas.")
                    return data
            except Exception as e:
                logging.error(f"Erro ao ler o cofre: {e}. Iniciando cofre vazio.")
                return {}
        return {}

    def get(self, text: str) -> str | None:
        """Busca uma tradução. Retorna a string traduzida ou None."""
        # TODO: MUDAR PARA HEX??
        return self.cache.get(text)

    def set(self, text: str, translation: str):
        """Salva a nova dupla na memória do cofre."""
        # TODO: MUDAR PARA HEX??
        self.cache[text] = translation

    def save(self):
        """Persiste a memória no disco."""
        os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
        with open(self.cache_file, 'w', encoding='utf-8') as f:
            json.dump(self.cache, f, ensure_ascii=False, indent=2)
        logging.info(f"Cofre trancado e salvo! Total de registros: {len(self.cache)}")