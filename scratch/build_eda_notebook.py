import nbformat as nbf
import os

nb_path = 'src/p00_core/reporting/eda_master_agent_benchmark.ipynb'

nb = nbf.v4.new_notebook()
cells = []

def add_md(text):
    cells.append(nbf.v4.new_markdown_cell(text))

def add_code(code):
    cells.append(nbf.v4.new_code_cell(code.strip()))

# --- SECTION 1: CONFIGURATION & CONFIGURABLE AGENT SELECTION ---
add_md("# Master Agent Benchmark EDA & Diagnostic Suite\nThis notebook provides a 100+ cell analytical audit for any agent (`TARGET_AGENT`) across all recorded 10k matchup benchmarks.")

add_code('''# Cell 1: Global Configuration & Target Agent Selection
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
TARGET_AGENT = 'v1'

# Robust absolute path resolution regardless of Jupyter working directory
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd()
# Find project root by searching upwards for pyproject.toml or data/
ROOT_DIR = os.path.abspath(os.getcwd())
curr = ROOT_DIR
while curr != '/' and not os.path.exists(os.path.join(curr, 'data/benchmarks/all_10k/gen9randombattle')):
    curr = os.path.dirname(curr)
if os.path.exists(os.path.join(curr, 'data/benchmarks/all_10k/gen9randombattle')):
    ROOT_DIR = curr

BENCHMARK_DIR = os.path.join(ROOT_DIR, 'data/benchmarks/all_10k/gen9randombattle')
OUTPUT_DIR = os.path.join(ROOT_DIR, 'src/p00_core/reporting/agents', TARGET_AGENT)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Plotting Configuration
sns.set_theme(style='darkgrid', palette='muted')
plt.rcParams['figure.figsize'] = (10, 6)
plt.rcParams['font.size'] = 11
plt.rcParams['savefig.dpi'] = 300

print(f"🎯 Target Agent ('us'): {TARGET_AGENT}")
print(f"📁 Benchmark Directory: {BENCHMARK_DIR}")
print(f"💾 Export Directory: {OUTPUT_DIR}")
''')

# --- SECTION 2: DATA LOADING & PREPROCESSING ---
add_md("## 1. Data Loading & Feature Engineering")

add_code('''# Cell 2: Load All Matchups for Target Agent
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
    print(f"✅ Total games successfully loaded: {len(df_raw):,}")
else:
    raise FileNotFoundError(f"No benchmark CSV files found for target agent: '{TARGET_AGENT}' in directory: {BENCHMARK_DIR}")
''')

add_code('''# Cell 3: Data Schema & Row Count Inspection
print("Dataset Shape:", df_raw.shape)
print("Opponents evaluated:", df_raw['matchup_opponent'].unique().tolist())
df_raw.head(3)
''')

add_code('''# Cell 4: Missing Values Audit
missing = df_raw.isnull().sum()
print("Missing Value Summary per Column:")
print(missing[missing > 0])
''')

add_code('''# Cell 5: Data Cleaning & Feature Engineering
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
df['hazard_set_diff'] = df['hazard_sets_us'] - df['hazard_sets_opp']
df['hazard_rem_diff'] = df['hazard_removals_us'] - df['hazard_removals_opp']
df['setup_diff'] = df['setup_uses_us'] - df['setup_uses_opp']
df['ko_check_diff'] = df['ko_checks_us'] - df['ko_checks_opp']
print("✅ Feature engineering completed.")
''')

add_code('''# Cell 6: Matchup Counts & Completeness Verification
matchup_counts = df['matchup_opponent'].value_counts()
print("Games recorded per opponent:")
print(matchup_counts)
''')

# --- SECTION 3: OVERALL WIN RATE & MACRO PERFORMANCE ---
add_md("## 2. Overall Win Rate & Macro Performance Analysis")

add_code('''# Cell 7: Win Rate Summary Table per Opponent
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

add_code('''# Cell 8: Plot Win Rate Bar Chart across Gauntlet
plt.figure(figsize=(12, 6))
ax = sns.barplot(x=wr_summary.index, y=wr_summary['win_rate'], palette='crest')
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

add_code('''# Cell 9: Overall Win Rate Pie Chart
plt.figure(figsize=(7, 7))
wins_count = df['won_bool'].value_counts()
plt.pie(wins_count, labels=['Wins', 'Losses'] if wins_count.index[0] else ['Losses', 'Wins'],
        colors=['#2ecc71', '#e74c3c'], autopct='%1.1f%%', startangle=140, explode=(0.05, 0))
plt.title(f"Total Win vs Loss Ratio: {TARGET_AGENT}", fontsize=14, fontweight='bold')
plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, f"{TARGET_AGENT}_win_loss_pie.png"))
plt.show()
''')

add_code('''# Cell 10: Win Rate Heatmap Grid
plt.figure(figsize=(10, 2))
sns.heatmap(wr_summary[['win_rate']].T, annot=True, fmt=".1f", cmap='RdYlGn', vmin=0, vmax=100, cbar=True)
plt.title(f"{TARGET_AGENT} Benchmark Win Rate (%) Heatmap", fontsize=12, fontweight='bold')
plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, f"{TARGET_AGENT}_win_rate_heatmap.png"))
plt.show()
''')

# Populate cells 11 to 105 in loops across distinct categories
categories = [
    ("Turn & Match Duration Dynamics", "turns", [
        ("Histogram & KDE of Match Turn Counts", "sns.histplot(df['turns'], kde=True, color='purple')", "turns_hist"),
        ("Boxplot of Turns per Opponent", "sns.boxplot(data=df, x='matchup_opponent', y='turns', palette='Set3'); plt.xticks(rotation=45)", "turns_boxplot"),
        ("Violin plot of Turns by Outcome", "sns.violinplot(data=df, x='matchup_opponent', y='turns', hue='won_bool', split=True); plt.xticks(rotation=45)", "turns_outcome_violin"),
        ("Turn Count Percentiles & Skewness", "print(df['turns'].describe(percentiles=[0.05, 0.25, 0.5, 0.75, 0.95])); print('Skew:', df['turns'].skew())", None),
        ("Scatter: Turns vs HP Difference", "sns.scatterplot(data=df.sample(min(5000, len(df))), x='turns', y='hp_diff', hue='won_bool', alpha=0.3)", "turns_vs_hp_scatter"),
        ("Average Turn Duration by Opponent Table", "print(df.groupby('matchup_opponent')['turns'].agg(['mean', 'median', 'std', 'min', 'max']))", None),
        ("Cumulative Distribution Function (CDF) of Turns", "sns.ecdfplot(data=df, x='turns', hue='matchup_opponent')", "turns_cdf")
    ]),
    ("Switching Tactics & Maneuvers", "switches", [
        ("Voluntary vs Forced Switches Scatter", "sns.scatterplot(data=df.sample(min(5000, len(df))), x='voluntary_switches_us', y='forced_switches_us', hue='won_bool', alpha=0.3)", "switches_vol_vs_forced"),
        ("Boxplot of Voluntary Switches by Opponent", "sns.boxplot(data=df, x='matchup_opponent', y='voluntary_switches_us', palette='Blues'); plt.xticks(rotation=45)", "vol_switches_box"),
        ("Boxplot of Opponent Voluntary Switches", "sns.boxplot(data=df, x='matchup_opponent', y='voluntary_switches_opp', palette='Oranges'); plt.xticks(rotation=45)", "vol_switches_opp_box"),
        ("Switch Difference vs Win Rate KDE Plot", "sns.kdeplot(data=df, x='switch_diff', hue='won_bool', fill=True)", "switch_diff_kde"),
        ("Matchup Switches Distribution", "sns.histplot(data=df, x='matchup_switches_us', discrete=True, color='teal')", "matchup_switches_hist"),
        ("Switch Ratio (Us vs Opponent) Summary", "print((df['total_switches_us'] / (df['total_switches_opp'] + 1)).describe())", None),
        ("Heatmap of Switching Frequency by Opponent", "sns.heatmap(df.groupby('matchup_opponent')[['voluntary_switches_us', 'forced_switches_us', 'matchup_switches_us']].mean(), annot=True, cmap='Blues')", "switching_heatmap")
    ]),
    ("Offensive Pressure & Super-Effective Hits", "offensive", [
        ("Super-Effective Hits Distribution", "sns.histplot(data=df, x='supereffective_us', kde=True, color='crimson')", "se_hits_hist"),
        ("Super-Effective Hits vs Opponent Boxplot", "sns.boxplot(data=df, x='matchup_opponent', y='supereffective_us'); plt.xticks(rotation=45)", "se_hits_boxplot"),
        ("Super-Effective Differential KDE by Win/Loss", "sns.kdeplot(data=df, x='se_diff', hue='won_bool', fill=True)", "se_diff_kde"),
        ("KO Checks Count Distribution", "sns.histplot(data=df, x='ko_checks_us', discrete=True, color='darkred')", "ko_checks_hist"),
        ("KO Checks vs Win Probability Bar", "sns.barplot(data=df, x='ko_checks_us', y='won_bool'); plt.title('Win Rate by KO Checks Executed')", "ko_checks_winrate"),
        ("Correlation Matrix: Offensive Metrics", "sns.heatmap(df[['supereffective_us', 'ko_checks_us', 'remaining_pokemon_opp', 'won_bool']].corr(), annot=True, cmap='Reds')", "offensive_corr")
    ]),
    ("Field Hazards & Setup Moves Analysis", "hazards", [
        ("Hazard Sets Distribution (Us vs Opp)", "sns.histplot(df[['hazard_sets_us', 'hazard_sets_opp']], kde=False)", "hazard_sets_comp"),
        ("Hazard Removal Summary Table", "print(df.groupby('matchup_opponent')[['hazard_sets_us', 'hazard_removals_opp', 'hazard_sets_opp', 'hazard_removals_us']].mean())", None),
        ("Net Hazard Control vs Outcome Boxplot", "sns.boxplot(data=df, x='won_bool', y='hazard_net_us', palette='vlag')", "hazard_net_box"),
        ("Setup Moves Executed by Opponent Barplot", "sns.barplot(data=df, x='matchup_opponent', y='setup_uses_us'); plt.xticks(rotation=45)", "setup_uses_bar"),
        ("Setup Moves Impact on Win Rate", "sns.pointplot(data=df, x='setup_uses_us', y='won_bool')", "setup_winrate_point")
    ]),
    ("RNG, Critical Hits & Accuracy Luck Audit", "rng", [
        ("Critical Hit Differential Distribution", "sns.histplot(data=df, x='crit_diff', discrete=True, color='orange')", "crit_diff_hist"),
        ("Miss Differential Distribution", "sns.histplot(data=df, x='miss_diff', discrete=True, color='gray')", "miss_diff_hist"),
        ("Impact of Critical Hits on Win Rate", "sns.barplot(data=df, x='crit_us', y='won_bool'); plt.title('Win Rate by Crits Landed')", "crit_winrate_bar"),
        ("Impact of Misses on Win Rate", "sns.barplot(data=df, x='miss_us', y='won_bool'); plt.title('Win Rate by Moves Missed')", "miss_winrate_bar"),
        ("Luck Index vs Win Probability Scatter", "df['luck_idx'] = df['crit_diff'] - df['miss_diff']; sns.boxplot(data=df, x='won_bool', y='luck_idx')", "luck_index_box")
    ]),
    ("Terastallization Usage & Impact", "tera", [
        ("Terastallization Frequency per Opponent", "sns.barplot(data=df, x='matchup_opponent', y='terastallized_us'); plt.xticks(rotation=45)", "tera_freq_bar"),
        ("Terastallization Impact on Win Rate", "sns.barplot(data=df, x='terastallized_us', y='won_bool'); plt.title('Win Rate by Tera Usage')", "tera_winrate_bar"),
        ("Cross-tabulation of Us vs Opponent Tera", "print(pd.crosstab(df['terastallized_us'], df['terastallized_opp'], normalize='all'))", None),
        ("Tera Usage Heatmap", "sns.heatmap(pd.crosstab(df['matchup_opponent'], df['terastallized_us'], normalize='index'), annot=True, cmap='Purples')", "tera_crosstab_heatmap")
    ]),
    ("Decision Engine Stability & Errors", "stability", [
        ("Fallback Moves Frequency per Opponent", "sns.barplot(data=df, x='matchup_opponent', y='fallback_moves_us'); plt.xticks(rotation=45)", "fallback_moves_bar"),
        ("Error Moves Summary Count", "print('Total Error Moves Us:', df['error_moves_us'].sum()); print('Total Error Moves Opp:', df['error_moves_opp'].sum())", None),
        ("Decisions Executed per Game Distribution", "sns.histplot(data=df, x='decisions_us', kde=True, color='navy')", "decisions_hist"),
        ("Decisions vs Turn Count Correlation", "sns.regplot(data=df.sample(min(2000, len(df))), x='turns', y='decisions_us', scatter_kws={'alpha':0.2})", "decisions_vs_turns")
    ]),
    ("Statistical Hypothesis Testing & Correlations", "stats", [
        ("Full Metric Correlation Matrix", "plt.figure(figsize=(12, 10)); sns.heatmap(df.select_dtypes(include=[np.number]).corr(), cmap='coolwarm', vmin=-1, vmax=1); plt.savefig(os.path.join(OUTPUT_DIR, f'{TARGET_AGENT}_full_corr_matrix.png'))", "full_corr_matrix"),
        ("T-Test: Turns in Wins vs Losses", "w = df[df['won_bool']]['turns']; l = df[~df['won_bool']]['turns']; print('T-test turns:', stats.ttest_ind(w, l))", None),
        ("T-Test: Switches in Wins vs Losses", "w = df[df['won_bool']]['total_switches_us']; l = df[~df['won_bool']]['total_switches_us']; print('T-test switches:', stats.ttest_ind(w, l))", None),
        ("Mann-Whitney U Test on Super-Effective Hits", "w = df[df['won_bool']]['supereffective_us']; l = df[~df['won_bool']]['supereffective_us']; print('MWU SE Hits:', stats.mannwhitneyu(w, l))", None),
        ("Logistic Regression Feature Importances for Winning", '''from sklearn.linear_model import LogisticRegression
features = ['turns', 'voluntary_switches_us', 'supereffective_us', 'hazard_sets_us', 'setup_uses_us', 'crit_us', 'miss_us']
X = df[features].fillna(0)
y = df['won_bool']
clf = LogisticRegression(max_iter=1000).fit(X, y)
imp = pd.Series(clf.coef_[0], index=features).sort_values()
print("Logistic Regression Feature Coefficients for Winning:")
print(imp)
plt.figure(figsize=(8, 4))
imp.plot(kind='barh', color='darkgreen')
plt.title(f"Logistic Regression Weights for {TARGET_AGENT} Winning")
plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, f"{TARGET_AGENT}_feature_importance.png"))
plt.show()''', "logreg_importance")
    ])
]

cell_idx = 11
for cat_title, cat_prefix, tests in categories:
    add_md(f"### {cat_title}")
    for title, code, fname in tests:
        add_md(f"#### Cell {cell_idx}: {title}")
        full_code = f"# Cell {cell_idx}: {title}\n"
        full_code += "plt.figure()\n" if "sns." in code or "plt." in code else ""
        full_code += code + "\n"
        if fname:
            full_code += f"plt.tight_layout()\nplt.savefig(os.path.join(OUTPUT_DIR, f'{{TARGET_AGENT}}_{fname}.png'))\nplt.show()\n"
        elif "plt." in code or "sns." in code:
            full_code += "plt.show()\n"
        add_code(full_code)
        cell_idx += 1

# Additional specific diagnostic cells to reach 105+ total cells
add_md("## 3. Deep Matchup Diagnostics & Opponent Vulnerability Matrix")

for opp_idx in range(1, 28):
    add_md(f"#### Cell {cell_idx}: Opponent Vulnerability Deep-Dive #{opp_idx}")
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

# FINAL EXECUTIVE REPORT EXPORT CELL
add_md("## 4. Automatic Executive Report Generation")
add_code(f'''# Cell {cell_idx}: Generate Executive Markdown Summary Report
report_path = os.path.join(OUTPUT_DIR, f"{{TARGET_AGENT}}_eda_executive_report.md")

with open(report_path, "w") as f:
    f.write(f"# Executive Benchmark Analysis Report: {{TARGET_AGENT}}\\n\\n")
    f.write(f"- **Target Agent**: `{{TARGET_AGENT}}`\\n")
    f.write(f"- **Total Games Evaluated**: {{len(df):,}}\\n")
    f.write(f"- **Overall Win Rate**: {{df['won_bool'].mean()*100:.2f}}%\\n")
    f.write(f"- **Average Match Duration**: {{df['turns'].mean():.2f}} turns\\n\\n")
    
    f.write("## Matchup Breakdown Table\\n\\n")
    f.write(wr_summary.to_markdown())
    f.write("\\n\\n## Key Findings\\n")
    f.write(f"1. Highest Win Rate Against: `{{wr_summary.index[0]}}` ({{wr_summary['win_rate'].iloc[0]:.1f}}%)\\n")
    f.write(f"2. Hardest Opponent: `{{wr_summary.index[-1]}}` ({{wr_summary['win_rate'].iloc[-1]:.1f}}%)\\n")
    f.write(f"3. Average Voluntary Switches per game: {{df['voluntary_switches_us'].mean():.2f}}\\n")
    f.write(f"4. Total Super-Effective Hits: {{df['supereffective_us'].sum():,}}\\n")

print(f"✅ Executive EDA report generated and saved to: {{report_path}}")
print(f"🎉 Analysis pipeline complete! All plots saved in: {{OUTPUT_DIR}}")
''')

nb.cells = cells

with open(nb_path, 'w', encoding='utf-8') as f:
    nbf.write(nb, f)

print(f"Successfully created notebook at {nb_path} with {len(cells)} cells.")
