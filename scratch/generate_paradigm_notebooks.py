import nbformat as nbf
import os

reporting_dir = 'src/p00_core/reporting'
os.makedirs(reporting_dir, exist_ok=True)

def create_base_cells(paradigm_title, default_agent, paradigm_desc):
    cells = []
    
    # Title & Header
    cells.append(nbf.v4.new_markdown_cell(f"# {paradigm_title}\n\n{paradigm_desc}"))
    
    # Cell 1: Global Configuration & Dynamic Path Resolution
    cell1_code = f'''# Cell 1: Configuration & Target Agent Selection
import os
import glob
import json
import ast
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats

# ── TARGET AGENT SELECTION ───────────────────────────────────────────────────
# Select agent to evaluate (Change to any agent within this paradigm)
TARGET_AGENT = '{default_agent}'

# Robust absolute path resolution for Jupyter environments
ROOT_DIR = os.path.abspath(os.getcwd())
curr = ROOT_DIR
while curr != '/' and not os.path.exists(os.path.join(curr, 'data/benchmarks/all_10k/gen9randombattle')):
    curr = os.path.dirname(curr)
if os.path.exists(os.path.join(curr, 'data/benchmarks/all_10k/gen9randombattle')):
    ROOT_DIR = curr

BENCHMARK_DIR = os.path.join(ROOT_DIR, 'data/benchmarks/all_10k/gen9randombattle')
OUTPUT_DIR = os.path.join(ROOT_DIR, 'src/p00_core/reporting/agents', TARGET_AGENT)
os.makedirs(OUTPUT_DIR, exist_ok=True)

sns.set_theme(style='darkgrid', palette='muted')
plt.rcParams['figure.figsize'] = (10, 6)
plt.rcParams['font.size'] = 11
plt.rcParams['savefig.dpi'] = 300

print(f"🎯 Target Agent ('us'): {{TARGET_AGENT}}")
print(f"📁 Benchmark Directory: {{BENCHMARK_DIR}}")
print(f"💾 Export Directory: {{OUTPUT_DIR}}")
'''
    cells.append(nbf.v4.new_code_cell(cell1_code.strip()))
    
    # Cell 2: Data Loading & Preprocessing
    cell2_code = '''# Cell 2: Data Loading & Preprocessing
files_us = sorted(glob.glob(os.path.join(BENCHMARK_DIR, f"{TARGET_AGENT}_vs_*.csv")))
print(f"Searching for matchup CSVs in: {BENCHMARK_DIR}")
print(f"Found {len(files_us)} matchup files where {TARGET_AGENT} is evaluated as 'us'")

dfs = []
for f in files_us:
    df_t = pd.read_csv(f)
    df_t['matchup_opponent'] = df_t['opponent']
    dfs.append(df_t)

if dfs:
    df_raw = pd.concat(dfs, ignore_index=True)
    print(f"✅ Total games loaded: {len(df_raw):,}")
else:
    raise FileNotFoundError(f"No benchmark CSV files found for target agent '{TARGET_AGENT}' in {BENCHMARK_DIR}")

df = df_raw.copy()
df['won_bool'] = df['won'].astype(bool)
df['hp_diff'] = df['remaining_pokemon_us'] - df['remaining_pokemon_opp']
df['fainted_diff'] = df['fainted_opp'] - df['fainted_us']
df['total_switches_us'] = df['voluntary_switches_us'] + df['forced_switches_us']
df['total_switches_opp'] = df['voluntary_switches_opp'] + df['forced_switches_opp']
df['switch_diff'] = df['total_switches_us'] - df['total_switches_opp']
df['vol_switch_diff'] = df['voluntary_switches_us'] - df['voluntary_switches_opp']
df['crit_diff'] = df['crit_us'] - df['crit_opp']
df['miss_diff'] = df['miss_us'] - df['miss_opp']
df['se_diff'] = df['supereffective_us'] - df['supereffective_opp']

# Safe calculation for hazard control
if 'hazard_sets_us' in df.columns and 'hazard_sets_opp' in df.columns:
    df['hazard_net_us'] = df['hazard_sets_us'] - df['hazard_sets_opp']
else:
    df['hazard_net_us'] = 0

df['setup_diff'] = df['setup_uses_us'] - df['setup_uses_opp'] if 'setup_uses_us' in df.columns else 0
df['ko_check_diff'] = df['ko_checks_us'] - df['ko_checks_opp'] if 'ko_checks_us' in df.columns else 0

print("✅ Feature engineering completed.")
'''
    cells.append(nbf.v4.new_code_cell(cell2_code.strip()))
    
    # Cell 3: Win Rate Summary Table
    cell3_code = '''# Cell 3: Win Rate & Performance Summary per Opponent
wr_summary = df.groupby('matchup_opponent').agg(
    games=('won_bool', 'count'),
    wins=('won_bool', 'sum'),
    win_rate=('won_bool', lambda x: x.mean() * 100),
    avg_turns=('turns', 'mean'),
    avg_hp_us=('remaining_pokemon_us', 'mean'),
    avg_hp_opp=('remaining_pokemon_opp', 'mean')
).sort_values(by='win_rate', ascending=False)

wr_summary.to_csv(os.path.join(OUTPUT_DIR, f"{TARGET_AGENT}_win_rate_summary.csv"))
print(f"🏆 Overall Win Rate: {df['won_bool'].mean()*100:.2f}% across {len(df):,} games")
wr_summary
'''
    cells.append(nbf.v4.new_code_cell(cell3_code.strip()))
    
    return cells, wr_summary_cell_code if 'wr_summary_cell_code' in locals() else None

print("Base helper initialized.")
