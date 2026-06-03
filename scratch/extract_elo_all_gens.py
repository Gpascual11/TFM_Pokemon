import json

notebook_path = "/home/sirp/Documents/MUDS/TFM_Pokemon/src/p01_heuristics/s01_singles/evaluation/reporting/eda_tournament.ipynb"

with open(notebook_path, "r", encoding="utf-8") as f:
    nb = json.load(f)

print("Extracting all printed Elo tables:")
for cell in nb["cells"]:
    if cell["cell_type"] == "code":
        outputs = cell.get("outputs", [])
        for out in outputs:
            text = out.get("text", [])
            if isinstance(text, list):
                text = "".join(text)
            elif isinstance(text, str):
                pass
            else:
                continue
            if "Bradley-Terry Elo Rankings:" in text:
                print(text)
                print("=" * 60)
