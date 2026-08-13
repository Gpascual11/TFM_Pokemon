import nbformat as nbf
import os

reporting_dir = 'src/p00_core/reporting'
os.makedirs(reporting_dir, exist_ok=True)

# ── HELPER FUNCTION TO ADD COMMON & SPECIALIZED CELLS ──
def build_notebook(nb_path, title, desc, default_agent, specialized_sections):
    nb = nbf.v4.new_notebook()
    cells = []

    def add_md(t): cells.append(nbf.v4.new_markdown_cell(t))
    def add_code(c): cells.append(nbf.v4.new_code_cell(c.strip()))

    add_md(f"# {title}\n\n{desc}")

    # Config Cell
    add_code(f'''# Cell 1: Global Configuration & Target Agent Selection
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
TARGET_AGENT = '{default_agent}'

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
''')

    # Data Loading
    add_code('''# Cell 2: Data Loading & Preprocessing
files_us = sorted(glob.glob(os.path.join(BENCHMARK_DIR, f"{TARGET_AGENT}_vs_*.csv")))
print(f"Searching in: {BENCHMARK_DIR}")
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
    raise FileNotFoundError(f"No benchmark CSV files found for target agent: '{TARGET_AGENT}'")

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

# Safe column initialization
df['hazard_net_us'] = (df['hazard_sets_us'] - df['hazard_sets_opp']) if 'hazard_sets_us' in df.columns else 0
df['setup_diff'] = (df['setup_uses_us'] - df['setup_uses_opp']) if 'setup_uses_us' in df.columns else 0
df['ko_check_diff'] = (df['ko_checks_us'] - df['ko_checks_opp']) if 'ko_checks_us' in df.columns else 0

print("✅ Data preprocessing and feature engineering complete.")
''')

    # Core Macro Analysis (Win rate, Turns, Switches)
    add_code('''# Cell 3: Overall Win Rate Summary
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
''')

    add_code('''# Cell 4: Win Rate Bar Chart across Gauntlet
plt.figure(figsize=(12, 6))
sns.barplot(x=wr_summary.index, y=wr_summary['win_rate'], palette='crest', hue=wr_summary.index, legend=False)
plt.axhline(50, color='red', linestyle='--', label='50% Win Rate Baseline')
plt.title(f"Win Rate (%) of {TARGET_AGENT} Across All Opponents", fontsize=14, fontweight='bold')
plt.ylabel("Win Rate (%)")
plt.xlabel("Opponent")
plt.xticks(rotation=45, ha='right')
plt.legend()
plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, f"{TARGET_AGENT}_win_rate_bar.png"))
plt.show()
''')

    add_code('''# Cell 5: Turns Boxplot Distribution
plt.figure(figsize=(12, 6))
sns.boxplot(data=df, x='matchup_opponent', y='turns', palette='Set3', hue='matchup_opponent', legend=False)
plt.xticks(rotation=45, ha='right')
plt.title(f"Match Duration (Turns) per Opponent ({TARGET_AGENT})")
plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, f"{TARGET_AGENT}_turns_boxplot.png"))
plt.show()
''')

    add_code('''# Cell 6: Switching Tactics (Voluntary vs Forced)
plt.figure(figsize=(12, 5))
sns.boxplot(data=df, x='matchup_opponent', y='voluntary_switches_us', palette='Blues', hue='matchup_opponent', legend=False)
plt.xticks(rotation=45, ha='right')
plt.title(f"Voluntary Switches per Game ({TARGET_AGENT})")
plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, f"{TARGET_AGENT}_voluntary_switches.png"))
plt.show()
''')

    cell_idx = 7
    # Specialized Paradigm-Specific Sections
    for section_title, tests in specialized_sections:
        add_md(f"## {section_title}")
        for test_title, code in tests:
            add_md(f"#### Cell {cell_idx}: {test_title}")
            full_code = f"# Cell {cell_idx}: {test_title}\n"
            full_code += code.strip()
            add_code(full_code)
            cell_idx += 1

    # Detailed Opponent Diagnostics Loop
    add_md("## Deep Opponent Diagnostic Matrix")
    for opp_idx in range(1, 28):
        add_md(f"#### Cell {cell_idx}: Matchup Diagnostic Rank #{opp_idx}")
        code = f'''# Cell {cell_idx}: Detailed Stats for Matchup Rank #{opp_idx}
if len(wr_summary) >= {opp_idx}:
    opp_name = wr_summary.index[{opp_idx-1}]
    df_sub = df[df['matchup_opponent'] == opp_name]
    print(f"=== MATCHUP DIAGNOSTIC #{opp_idx}: {{TARGET_AGENT}} vs {{opp_name}} ===")
    print(f"Win Rate: {{df_sub['won_bool'].mean()*100:.2f}}% ({{len(df_sub):,}} games)")
    print(f"Avg Turns: {{df_sub['turns'].mean():.2f}}")
    print(f"Avg HP Us: {{df_sub['remaining_pokemon_us'].mean():.2f}} | Opp: {{df_sub['remaining_pokemon_opp'].mean():.2f}}")
    print(f"Avg Voluntary Switches Us: {{df_sub['voluntary_switches_us'].mean():.2f}} | Opp: {{df_sub['voluntary_switches_opp'].mean():.2f}}")
'''
        add_code(code)
        cell_idx += 1

    # Executive Report Generation Cell
    add_md("## Automatic Executive Report Export")
    add_code(f'''# Cell {cell_idx}: Generate Executive Markdown Summary Report
report_path = os.path.join(OUTPUT_DIR, f"{{TARGET_AGENT}}_eda_executive_report.md")
best_opp = wr_summary.index[0]
worst_opp = wr_summary.index[-1]
best_wr = wr_summary['win_rate'].iloc[0]
worst_wr = wr_summary['win_rate'].iloc[-1]

content = f"""# Executive Benchmark Analysis Report: {{TARGET_AGENT}}

- **Target Agent**: `{{TARGET_AGENT}}`
- **Total Games Evaluated**: {{len(df):,}}
- **Overall Win Rate**: {{df['won_bool'].mean()*100:.2f}}%
- **Average Match Duration**: {{df['turns'].mean():.2f}} turns

## Matchup Breakdown Table

{{wr_summary.to_markdown()}}

## Key Findings
1. Highest Win Rate Against: `{{best_opp}}` ({{best_wr:.1f}}%)
2. Hardest Opponent: `{{worst_opp}}` ({{worst_wr:.1f}}%)
3. Average Voluntary Switches per game: {{df['voluntary_switches_us'].mean():.2f}}
4. Total Super-Effective Hits: {{df['supereffective_us'].sum():,}}
"""

with open(report_path, 'w') as f:
    f.write(content)

print(f"✅ Executive EDA report generated and saved to: {{report_path}}")
print(f"🎉 Analysis pipeline complete! All plots saved in: {{OUTPUT_DIR}}")
''')

    nb.cells = cells
    with open(nb_path, 'w', encoding='utf-8') as f:
        nbf.write(nb, f)
    print(f"Successfully generated {nb_path} ({len(cells)} cells)")


# ── 1. NOTEBOOK 1: HEURISTIC BASELINES (v1 - v14) ──
sections_v1_v14 = [
    ("Heuristic Rule Execution & Fallback Audit", [
        ("Fallback Move Execution Distribution", "plt.figure()\nsns.histplot(data=df, x='fallback_moves_us', discrete=True, color='darkred')\nplt.title('Fallback Moves Executed by Heuristic Agent')\nplt.tight_layout()\nplt.savefig(os.path.join(OUTPUT_DIR, f'{TARGET_AGENT}_fallback_moves.png'))\nplt.show()"),
        ("Error Moves Summary", "print('Total Decision Engine Error Moves (Us):', df['error_moves_us'].sum())"),
        ("Matchup Switch Rule Frequency", "plt.figure()\nsns.barplot(data=df, x='matchup_opponent', y='matchup_switches_us', hue='matchup_opponent', legend=False)\nplt.xticks(rotation=45, ha='right')\nplt.title('Matchup Rule Switches Triggered per Opponent')\nplt.tight_layout()\nplt.savefig(os.path.join(OUTPUT_DIR, f'{TARGET_AGENT}_matchup_switches.png'))\nplt.show()"),
        ("Super-Effective Attack Execution Rate", "plt.figure()\nsns.boxplot(data=df, x='matchup_opponent', y='supereffective_us', hue='matchup_opponent', legend=False)\nplt.xticks(rotation=45, ha='right')\nplt.title('Super-Effective Hits Landed per Game')\nplt.tight_layout()\nplt.savefig(os.path.join(OUTPUT_DIR, f'{TARGET_AGENT}_se_hits.png'))\nplt.show()"),
        ("KO Check Execution vs Outcome", "plt.figure()\nsns.barplot(data=df, x='ko_checks_us', y='won_bool')\nplt.title('Win Rate by KO Check Executions')\nplt.tight_layout()\nplt.savefig(os.path.join(OUTPUT_DIR, f'{TARGET_AGENT}_ko_checks_winrate.png'))\nplt.show()")
    ])
]
build_notebook('src/p00_core/reporting/eda_heuristics_v1_v14.ipynb', 
               'EDA Benchmark Suite: Heuristic Agents (v1 – v14)', 
               'Dedicated analytical suite to audit heuristic rules, decision engine fallbacks, matchup switching rules, and rule-based KO execution.', 
               'v1', sections_v1_v14)


# ── 2. NOTEBOOK 2: MINIMAX SEARCH AGENTS (v15 - v17) ──
sections_v15_v17 = [
    ("Minimax Lookahead & Search Dynamics", [
        ("Search Time / Decisions Latency Audit", "plt.figure()\nsns.histplot(data=df, x='decisions_us', kde=True, color='teal')\nplt.title('Minimax Decisions Executed per Game')\nplt.tight_layout()\nplt.savefig(os.path.join(OUTPUT_DIR, f'{TARGET_AGENT}_minimax_decisions.png'))\nplt.show()"),
        ("Minimax Switching vs Defensive Horizon", "plt.figure()\nsns.boxplot(data=df, x='matchup_opponent', y='voluntary_switches_us', palette='Blues', hue='matchup_opponent', legend=False)\nplt.xticks(rotation=45, ha='right')\nplt.title('Minimax Voluntary Switches (1-Ply Lookahead)')\nplt.tight_layout()\nplt.savefig(os.path.join(OUTPUT_DIR, f'{TARGET_AGENT}_minimax_switches.png'))\nplt.show()"),
        ("Hybrid Heuristic Override Audit (v17 Hybrid)", "if 'ko_checks_us' in df.columns:\n    plt.figure()\n    sns.barplot(data=df, x='matchup_opponent', y='ko_checks_us', hue='matchup_opponent', legend=False)\n    plt.xticks(rotation=45, ha='right')\n    plt.title('Hybrid Safety Override Triggers per Opponent')\n    plt.tight_layout()\n    plt.savefig(os.path.join(OUTPUT_DIR, f'{TARGET_AGENT}_hybrid_overrides.png'))\n    plt.show()"),
        ("Minimax Super-Effective Exploitation", "plt.figure()\nsns.scatterplot(data=df.sample(min(5000, len(df))), x='supereffective_us', y='remaining_pokemon_opp', hue='won_bool', alpha=0.4)\nplt.title('Super-Effective Pressure vs Opponent Fainted Pokemon')\nplt.tight_layout()\nplt.savefig(os.path.join(OUTPUT_DIR, f'{TARGET_AGENT}_se_vs_fainted.png'))\nplt.show()"),
        ("1-Ply Minimax Horizon Limitation Audit (Turns in Losses)", "plt.figure()\nsns.violinplot(data=df, x='won_bool', y='turns', palette='Set2')\nplt.title('Game Duration (Turns) in Minimax Wins vs Losses')\nplt.tight_layout()\nplt.savefig(os.path.join(OUTPUT_DIR, f'{TARGET_AGENT}_minimax_turns_outcome.png'))\nplt.show()")
    ])
]
build_notebook('src/p00_core/reporting/eda_minimax_v15_v17.ipynb', 
               'EDA Benchmark Suite: Minimax Search Agents (v15 – v17)', 
               'Dedicated analytical suite to audit 1-ply Minimax evaluation functions, horizon effects, search latency, and hybrid safety overrides.', 
               'v15', sections_v15_v17)


# ── 3. NOTEBOOK 3: MCTS AGENTS (v18 - v20) ──
sections_v18_v20 = [
    ("MCTS Tree Exploration & Simulation Analysis", [
        ("MCTS Match Duration Dynamics (Deep Horizon)", "plt.figure()\nsns.histplot(data=df, x='turns', kde=True, color='purple')\nplt.title('MCTS Game Duration (Turns) Distribution')\nplt.tight_layout()\nplt.savefig(os.path.join(OUTPUT_DIR, f'{TARGET_AGENT}_mcts_turns.png'))\nplt.show()"),
        ("Long-Term Hazard Setup Valuation (Setup & Hazards)", "plt.figure()\nsns.boxplot(data=df, x='matchup_opponent', y='hazard_net_us', palette='Greens', hue='matchup_opponent', legend=False)\nplt.xticks(rotation=45, ha='right')\nplt.title('Net Hazard Control (MCTS Long-Term Setup Value)')\nplt.tight_layout()\nplt.savefig(os.path.join(OUTPUT_DIR, f'{TARGET_AGENT}_mcts_hazards.png'))\nplt.show()"),
        ("MCTS Rollout Switch Exploration", "plt.figure()\nsns.kdeplot(data=df, x='voluntary_switches_us', hue='won_bool', fill=True)\nplt.title('MCTS Voluntary Switch Frequency in Wins vs Losses')\nplt.tight_layout()\nplt.savefig(os.path.join(OUTPUT_DIR, f'{TARGET_AGENT}_mcts_switches_kde.png'))\nplt.show()"),
        ("IS-MCTS Information Set Determinization Impact", "plt.figure()\nsns.scatterplot(data=df.sample(min(1000, len(df))), x='turns', y='hp_diff', hue='won_bool', alpha=0.5)\nplt.title('MCTS Turn Duration vs End Game HP Advantage')\nplt.tight_layout()\nplt.savefig(os.path.join(OUTPUT_DIR, f'{TARGET_AGENT}_mcts_hp_diff.png'))\nplt.show()"),
        ("MCTS Hybrid Rule Interventions (v20 Hybrid)", "if 'ko_checks_us' in df.columns:\n    print('MCTS KO Guards executed:', df['ko_checks_us'].sum())")
    ])
]
build_notebook('src/p00_core/reporting/eda_mcts_v18_v20.ipynb', 
               'EDA Benchmark Suite: Monte Carlo Tree Search Agents (v18 – v20)', 
               'Dedicated analytical suite to audit Information Set MCTS rollouts, long-term hazard/setup valuation, deep lookahead strategy, and IS-determinization.', 
               'v18', sections_v18_v20)


# ── 4. NOTEBOOK 4: IMITATION LEARNING & POLICY GRADIENT (v21 - v22) ──
sections_v21_v22 = [
    ("Neural Policy & Imitation Strategy Audit", [
        ("XGBoost / Neural Switching Behavior", "plt.figure()\nsns.histplot(data=df, x='voluntary_switches_us', discrete=True, color='indigo')\nplt.title('Imitation Model Voluntary Switch Frequency')\nplt.tight_layout()\nplt.savefig(os.path.join(OUTPUT_DIR, f'{TARGET_AGENT}_imitation_switches.png'))\nplt.show()"),
        ("Offensive Super-Effective Execution Ratio", "plt.figure()\nsns.boxplot(data=df, x='matchup_opponent', y='supereffective_us', palette='Reds', hue='matchup_opponent', legend=False)\nplt.xticks(rotation=45, ha='right')\nplt.title('Super-Effective Hits Executed by Imitation Model')\nplt.tight_layout()\nplt.savefig(os.path.join(OUTPUT_DIR, f'{TARGET_AGENT}_imitation_se_hits.png'))\nplt.show()"),
        ("Terastallization Policy Prediction Impact", "plt.figure()\nsns.barplot(data=df, x='terastallized_us', y='won_bool')\nplt.title('Win Rate when Imitation Agent Terastallizes')\nplt.tight_layout()\nplt.savefig(os.path.join(OUTPUT_DIR, f'{TARGET_AGENT}_imitation_tera_winrate.png'))\nplt.show()"),
        ("Feature Importance & Policy Weight Analysis", "from sklearn.ensemble import RandomForestClassifier\nfeatures = ['turns', 'voluntary_switches_us', 'supereffective_us', 'fainted_diff']\nX = df[features].fillna(0)\ny = df['won_bool']\nclf = RandomForestClassifier(n_estimators=100, random_state=42).fit(X, y)\nimp = pd.Series(clf.feature_importances_, index=features).sort_values()\nplt.figure(figsize=(8, 4))\nimp.plot(kind='barh', color='darkblue')\nplt.title(f'Random Forest Feature Importance for {TARGET_AGENT} Outcomes')\nplt.tight_layout()\nplt.savefig(os.path.join(OUTPUT_DIR, f'{TARGET_AGENT}_rf_importance.png'))\nplt.show()"),
        ("Imitation vs Expert Baseline Comparison", "plt.figure()\nsns.barplot(data=df, x='matchup_opponent', y='won_bool', palette='vlag', hue='matchup_opponent', legend=False)\nplt.axhline(0.5, color='red', linestyle='--')\nplt.xticks(rotation=45, ha='right')\nplt.title(f'Imitation Agent ({TARGET_AGENT}) Win Rate Matrix')\nplt.tight_layout()\nplt.savefig(os.path.join(OUTPUT_DIR, f'{TARGET_AGENT}_imitation_wr_matrix.png'))\nplt.show()")
    ])
]
build_notebook('src/p00_core/reporting/eda_imitation_v21_v22.ipynb', 
               'EDA Benchmark Suite: Imitation & Policy Learning (v21 – v22)', 
               'Dedicated analytical suite to audit XGBoost and neural network policy predictions, expert imitation accuracy, feature importances, and switching generalization.', 
               'v21', sections_v21_v22)

print("🎉 All 4 paradigm notebooks built successfully in src/p00_core/reporting/")
