import os
from pathlib import Path
import pandas as pd

DATA_DIR = Path("/home/sirp/Documents/MUDS/TFM_Pokemon/data/1_vs_1/benchmarks_all_10k")

all_elos = {}
for i in range(1, 10):
    gen = f"gen{i}randombattle"
    f_path = DATA_DIR / gen / "elo_summary.csv"
    if f_path.exists():
        df = pd.read_csv(f_path)
        # Columns are agent, elo
        # Let's anchor random to 1000 if not already, wait, let's see what is inside
        all_elos[gen] = df.set_index('agent')['elo']
    else:
        print(f"File not found: {f_path}")

df_all = pd.DataFrame(all_elos)
# Sort index by gen 9 Elo
if 'gen9randombattle' in df_all.columns:
    df_all = df_all.sort_values(by='gen9randombattle', ascending=False)
print(df_all.round(1).to_string())
