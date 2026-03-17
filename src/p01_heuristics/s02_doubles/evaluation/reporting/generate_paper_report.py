"""Paper-Ready Visual Report Generator for Doubles Heuristic Results.
Adapted from Singles version for Doubles-specific data structures.
"""

import sys
from pathlib import Path
import argparse
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

# ---------------------------------------------------------------------------
# STYLE CONFIGURATION (Premium Scientific Style)
# ---------------------------------------------------------------------------

COLORS = {
    "primary": "#1f77b4",      # Steel Blue
    "secondary": "#9467bd",    # Muted Purple
    "success": "#2ca02c",      # Forest Green
    "danger": "#d62728",       # Brick Red
    "warning": "#ff7f0e",      # Safety Orange
    "dark": "#1a1a1b",         # Near Black for text
    "light": "#fdfdfd",        # Off-white
    "gray": "#7f7f7f",         # Neutral Gray
    "background": "#ffffff",
    "grid": "#e1e1e1"
}

RD_YL_GN_PREMIUM = sns.diverging_palette(15, 135, s=70, l=55, n=256, as_cmap=True)
BLUES_PREMIUM = sns.cubehelix_palette(start=.5, rot=-.5, as_cmap=True)

def apply_premium_style():
    sns.set_theme(style="white", context="paper")
    plt.rcParams.update({
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.linewidth": 0.8,
        "axes.edgecolor": COLORS["dark"],
        "axes.grid": True,
        "grid.color": COLORS["grid"],
        "grid.linestyle": ":",
        "grid.alpha": 0.6,
        "axes.axisbelow": True,
        "font.family": "serif",
        "font.serif": ["Times New Roman", "DejaVu Serif", "serif"],
        "axes.titlesize": 16,
        "axes.titleweight": "bold",
        "axes.labelsize": 12,
        "axes.labelweight": "medium",
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
        "legend.fontsize": 10,
        "savefig.dpi": 400,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.02,
    })

def get_display_name(name: str) -> str:
    if not isinstance(name, str):
        return str(name)
    name_lower = name.lower()
    if name_lower in {"random", "max_power", "simple_heuristic"}:
        return f"(B) {name}"
    if name_lower.startswith("v") and len(name_lower) > 1 and name_lower[1:].isdigit():
        return f"(H) {name}"
    return name

def get_category_color(name_with_prefix: str) -> str:
    if "(B)" in name_with_prefix: return COLORS["primary"]
    if "(H)" in name_with_prefix: return COLORS["success"]
    return COLORS["dark"]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
AGENT_ORDER = ["v1", "v2", "v3", "v4", "v5", "random", "max_power", "simple_heuristic"]
BASELINES = {"random", "max_power", "simple_heuristic"}

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def load_all_data(data_dir: Path) -> pd.DataFrame:
    files = sorted(data_dir.glob("*.csv"))
    if not files:
        raise FileNotFoundError(f"No CSV files found in '{data_dir}'.")
    frames = []
    for f in files:
        df = pd.read_csv(f)
        # Standardize columns for Doubles
        if "heuristic" in df.columns: df = df.rename(columns={"heuristic": "agent"})
        if "opponent_type" in df.columns: df = df.rename(columns={"opponent_type": "opponent"})
        frames.append(df)
    return pd.concat(frames, ignore_index=True)

def _reorder(series: pd.Series, order: list[str]) -> list[str]:
    present = {str(x) for x in series.unique()}
    return [x for x in order if x in present] + sorted([x for x in present if x not in order])

def _pivot(df: pd.DataFrame, value: str, agent_order: list[str], opp_order: list[str]) -> pd.DataFrame:
    summary = df.groupby(["agent", "opponent"])[value].mean().reset_index()
    if value == "won": summary[value] *= 100
    pivot = summary.pivot(index="agent", columns="opponent", values=value)
    return pivot.reindex(index=agent_order, columns=opp_order)

def save_latex_table(df: pd.DataFrame, path: Path, caption: str, label: str):
    latex = df.to_latex(
        index=True, float_format="%.1f", caption=caption, label=label,
        position="htbp", escape=False, column_format="l" + "c" * (len(df.columns)),
    )
    latex = latex.replace("\\toprule", "\\hline").replace("\\midrule", "\\hline").replace("\\bottomrule", "\\hline")
    with open(path, "w") as f: f.write(latex)
    print(f"📄 LaTeX table saved to: {path}")

# ---------------------------------------------------------------------------
# Main Generator
# ---------------------------------------------------------------------------
def generate_doubles_report(data_dir: Path, output_dir: Path):
    apply_premium_style()
    df = load_all_data(data_dir)
    df["win_pct"] = df["won"] * 100.0
    
    agents_raw = _reorder(df["agent"], AGENT_ORDER)
    opps_raw = _reorder(df["opponent"], AGENT_ORDER)
    display_baselines = {get_display_name(x) for x in BASELINES}

    output_dir.mkdir(parents=True, exist_ok=True)
    tex_dir = output_dir / "latex_tables"
    tex_dir.mkdir(parents=True, exist_ok=True)

    # 1. Win-Rate Heatmap
    wr_pivot = _pivot(df, "won", agents_raw, opps_raw)
    wr_tex = wr_pivot.copy()
    wr_tex.index = [get_display_name(x).replace("_", "\\_") for x in wr_tex.index]
    wr_tex.columns = [get_display_name(x).replace("_", "\\_") for x in wr_tex.columns]
    save_latex_table(wr_tex, tex_dir / "win_rate_matrix.tex", "Doubles Matchup Win-Rate Matrix (%)", "tab:doubles_win_rate")

    fig, ax = plt.subplots(figsize=(10, 8))
    wr_display = wr_pivot.copy()
    wr_display.index = [get_display_name(x) for x in wr_display.index]
    wr_display.columns = [get_display_name(x) for x in wr_display.columns]
    sns.heatmap(wr_display, annot=True, fmt=".1f", cmap=RD_YL_GN_PREMIUM, vmin=0, vmax=100, ax=ax)
    plt.savefig(output_dir / "01_win_rate_heatmap.png")
    plt.close()

    # 2. Ranking
    fig, ax = plt.subplots(figsize=(8, 6))
    ranking_df = df.groupby("agent")["win_pct"].mean().reindex(agents_raw).sort_values(ascending=True)
    labels = [get_display_name(x) for x in ranking_df.index]
    ax.barh(labels, ranking_df.values, color=[get_category_color(x) for x in labels])
    plt.savefig(output_dir / "02_agent_ranking.png")
    plt.close()

    # 3. Fainted Diff
    f_opp = _pivot(df, "fainted_opp", agents_raw, opps_raw)
    f_us = _pivot(df, "fainted_us", agents_raw, opps_raw)
    fd = f_opp - f_us
    save_latex_table(fd, tex_dir / "fainted_diff.tex", "Mean Fainted Pokémon Differential (Opponent - Us)", "tab:doubles_fainted_diff")

    # 4. Turns
    turns_pivot = _pivot(df, "turns", agents_raw, opps_raw)
    save_latex_table(turns_pivot, tex_dir / "battle_duration.tex", "Mean Battle Duration (Turns)", "tab:doubles_turns")

    print(f"✅ Doubles Paper report generated in: {output_dir}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--gen", type=int, default=9)
    args = parser.parse_args()
    
    data_path = Path(f"data/2_vs_2/benchmarks/unified_gen{args.gen}randomdoublesbattle")
    out_path = Path(f"src/p01_heuristics/s02_doubles/results/heatmaps_gen{args.gen}")
    generate_doubles_report(data_path, out_path)
