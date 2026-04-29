import os, zipfile, logging

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

# Reconstroi o .idml

class IDMLBuilder:
    def __init__(self, temp_dir: str, xml_trees: dict):
        self.temp_dir = temp_dir
        self.xml_trees = xml_trees

    def inject_translations(self, payload: list, translations: list):
        """
        Injeta as traduções de volta nos nós XML que estão na memória.
        A precisão de índice garante que a formatação original do InDesign não quebre.
        """
        if len(payload) != len(translations):
            raise ValueError(f"Erro Crítico de Injeção: Temos {len(payload)} nós, mas {len(translations)} traduções.")
        
        logging.info("Injetando traduções na árvore XML em memória...")
        for i in range(len(payload)):
            node = payload[i]["node"]
            # Substitui o texto em inglês pelo português
            node.text = translations[i]

    def save_xml_files(self):
        """Salva as árvores XML modificadas de volta no temp_dir."""
        logging.info("Sobrescrevendo arquivos XML com os novos dados...")
        for file_path, tree in self.xml_trees.items():
            tree.write(file_path, encoding="UTF-8", xml_declaration=True, standalone="yes")

    def repackage(self, output_path: str):
        """Recompacta o diretório temporário em um novo arquivo .idml limpo."""
        logging.info(f"Empacotando arquivo final...")
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(self.temp_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, self.temp_dir)
                    zipf.write(file_path, arcname)
        logging.info("Reempacotamento concluído com sucesso!")