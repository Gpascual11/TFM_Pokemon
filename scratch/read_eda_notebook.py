import json

notebook_path = "/home/sirp/Documents/MUDS/TFM_Pokemon/src/p01_heuristics/s01_singles/evaluation/reporting/eda_tournament.ipynb"

with open(notebook_path, "r", encoding="utf-8") as f:
    nb = json.load(f)

print("Cells containing Elo or ranking details:")
for cell in nb["cells"]:
    if cell["cell_type"] == "code":
        # Check if outputs contain 1817 or "1817"
        outputs = cell.get("outputs", [])
        for out in outputs:
            text = out.get("text", [])
            if isinstance(text, list):
                text = "".join(text)
            elif isinstance(text, str):
                pass
            else:
                continue
            if "1817" in text or "v12" in text and "elo" in text.lower():
                print("Code Output:")
                print(text[:1000])
                print("-" * 50)
    elif cell["cell_type"] == "markdown":
        source = "".join(cell.get("source", []))
        if "1817" in source or "elo" in source.lower():
            print("Markdown Source:")
            print(source[:1000])
            print("-" * 50)
