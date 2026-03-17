"""Generalized Elo Ranking Generator for Paper Reporting.
Calculates Elo from benchmark CSV files and saves plots/LaTeX tables.
"""

import os
import glob
import pandas as pd
import numpy as np
import argparse
from pathlib import Path
import matplotlib.pyplot as plt
from sklearn.linear_model import LogisticRegression

# ---------------------------------------------------------------------------
# STYLE CONFIGURATION (Matching generate_paper_report.py)
# ---------------------------------------------------------------------------

COLORS = {
    "primary": "#1f77b4",
    "success": "#2ca02c",
    "secondary": "#9467bd",
    "dark": "#1a1a1b",
    "grid": "#e1e1e1"
}

def apply_premium_style():
    plt.rcParams.update({
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.color": "#e1e1e1",
        "grid.linestyle": ":",
        "font.family": "serif",
        "font.serif": ["Times New Roman", "DejaVu Serif", "serif"],
        "axes.titlesize": 16,
        "axes.labelsize": 12,
        "savefig.dpi": 400,
        "savefig.bbox": "tight",
    })

def get_display_name(name: str) -> str:
    if not isinstance(name, str): return str(name)
    nl = name.lower()
    if nl in {"random", "max_power", "simple_heuristic"}: return f"(B) {name}"
    if nl.startswith("v") and len(nl) > 1 and nl[1:].isdigit(): return f"(H) {name}"
    if nl in {"abyssal", "one_step", "safe_one_step", "pokechamp", "pokellmon"}: return f"(C) {name}"
    return name

def get_category_color(name_with_prefix: str) -> str:
    if "(B)" in name_with_prefix: return COLORS["primary"]
    if "(H)" in name_with_prefix: return COLORS["success"]
    if "(C)" in name_with_prefix: return COLORS["secondary"]
    return COLORS["dark"]

# ---------------------------------------------------------------------------
# ELO CALCULATION
# ---------------------------------------------------------------------------

def calculate_elo(df: pd.DataFrame, SCALE: int=400, BASE: int=10, INIT_RATING: int=1000):
    models = pd.concat([df['model_a'], df['model_b']]).unique()
    models_series = pd.Series(np.arange(len(models)), index=models)
    df_eval = pd.concat([df, df], ignore_index=True)
    
    p = len(models_series)
    n = df_eval.shape[0]
    X = np.zeros([n, p])
    X[np.arange(n), models_series[df_eval["model_a"]]] = +np.log(BASE)
    X[np.arange(n), models_series[df_eval["model_b"]]] = -np.log(BASE)

    Y = np.zeros(n)
    Y[df_eval["winner"] == "model_a"] = 1.0

    lr = LogisticRegression(fit_intercept=False, C=1e6) # High C for MLE
    lr.fit(X, Y)

    elo_scores = SCALE * lr.coef_[0] + INIT_RATING
    return pd.Series(elo_scores, index=models_series.index).sort_values(ascending=False)

# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def generate_elo_report(data_dir: Path, output_dir: Path, title: str):
    apply_premium_style()
    csv_files = sorted(data_dir.glob("*.csv"))
    if not csv_files:
        print(f"No CSV files in {data_dir}")
        return

    all_battles = []
    for f in csv_files:
        df = pd.read_csv(f)
        col_map = {"heuristic": "agent", "opponent_type": "opponent"}
        df = df.rename(columns=col_map)
        
        if df.empty or 'won' not in df.columns or 'agent' not in df.columns:
            continue
            
        matchup_df = pd.DataFrame({
            'model_a': df['agent'],
            'model_b': df['opponent'],
            'winner': df['won'].apply(lambda w: 'model_a' if w == 1 else 'model_b')
        })
        all_battles.append(matchup_df)

    if not all_battles: return
    combined_df = pd.concat(all_battles, ignore_index=True)
    elo_ratings = calculate_elo(combined_df)

    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Bar Plot
    fig, ax = plt.subplots(figsize=(10, 6))
    display_names = [get_display_name(x) for x in elo_ratings.index]
    colors = [get_category_color(x) for x in display_names]
    
    bars = ax.bar(display_names, elo_ratings.values, color=colors, edgecolor='black', alpha=0.8)
    ax.set_title(title)
    ax.set_ylabel("Elo Rating (Baseline = 1000)")
    plt.xticks(rotation=45, ha='right')
    
    # Baseline line
    ax.axhline(1000, color='red', linestyle='--', alpha=0.5, label="1000 Baseline")
    
    plt.savefig(output_dir / "elo_ranking_plot.png")
    plt.close()

    # 2. LaTeX Table
    tex_df = pd.DataFrame({"Agent": display_names, "Elo Rating": elo_ratings.values})
    tex_df["Agent"] = tex_df["Agent"].str.replace("_", "\\_")
    
    latex = tex_df.to_latex(index=False, float_format="%.0f", 
                           caption=f"Elo Ranking - {title}", 
                           label=f"tab:elo_{title.lower().replace(' ', '_')}",
                           position="htbp", column_format="lc")
    
    tex_path = output_dir / "elo_ranking.tex"
    with open(tex_path, "w") as f: f.write(latex)
    
    print(f"✅ Elo report generated for {title}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["singles", "doubles"], required=True)
    parser.add_argument("--gen", type=int, default=9)
    args = parser.parse_args()

    if args.mode == "singles":
        data_path = Path(f"data/1_vs_1/benchmarks/unified_gen{args.gen}randombattle")
        out_path = Path(f"src/p01_heuristics/s01_singles/evaluation/results/elo_gen{args.gen}")
        title = f"Singles Gen {args.gen}"
    else:
        data_path = Path(f"data/2_vs_2/benchmarks/unified_gen{args.gen}randomdoublesbattle")
        out_path = Path(f"src/p01_heuristics/s02_doubles/results/elo_gen{args.gen}")
        title = f"Doubles Gen {args.gen}"

    generate_elo_report(data_path, out_path, title)
