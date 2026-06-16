import json

notebook_path = "/home/sirp/Documents/MUDS/TFM_Pokemon/src/p00_core/reporting/eda_tournament.ipynb"

with open(notebook_path, encoding="utf-8") as f:
    nb = json.load(f)

for idx, cell in enumerate(nb["cells"]):
    if cell["cell_type"] == "code":
        source = "".join(cell.get("source", []))
        if "calculate_elo" in source or "elo" in source.lower():
            print(f"Cell {idx}:")
            print(source)
            print("-" * 50)
