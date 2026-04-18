"""Full Visual Report Generator for Pokechamp Benchmark Results.

Optimized for Paper Inclusion: No titles, tight margins, and LaTeX output.
Targets the 'unified' dataset folder.
"""

from __future__ import annotations

import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Package bootstrap
# ---------------------------------------------------------------------------
_DIR = Path(__file__).parent.resolve()
_REPORTING = _DIR.parent
_EVAL = _REPORTING.parent
_SINGLES = _EVAL.parent
_SRC = _SINGLES.parent.parent
_ROOT = _SRC.parent

if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import argparse
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from p01_heuristics.s01_singles.evaluation.reporting.plots.styling import (
    apply_premium_style, 
    finalize_plot, 
    get_display_name, 
    RD_YL_GN_PREMIUM, 
    BLUES_PREMIUM, 
    COLORS,
    get_category_color
)

# Use the unified folder as the source of truth
DEFAULT_DATA_DIR = Path("data/1_vs_1/benchmarks/unified")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
AGENT_ORDER = [
    "v1", "v2", "v3", "v4", "v5", "v6",
    "random", "max_power", "simple_heuristic",
    "abyssal", "one_step", "safe_one_step",
    "pokechamp", "pokellmon",
]
OPPONENT_ORDER = [
    "v1", "v2", "v3", "v4", "v5", "v6",
    "random", "max_power", "simple_heuristic",
    "abyssal", "one_step", "safe_one_step",
]
BASELINES = {"random", "max_power", "simple_heuristic"}

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def load_all_data(data_dir: Path) -> pd.DataFrame:
    """Load and concatenate all CSVs found in *data_dir*."""
    files = sorted(data_dir.glob("*.csv"))
    if not files:
        raise FileNotFoundError(
            f"No CSV files found in '{data_dir}'."
        )

    frames = []
    for f in files:
        try:
            df = pd.read_csv(f)
            # Standardize columns: the unified format uses 'heuristic' for the agent
            if "heuristic" in df.columns:
                df = df.rename(columns={"heuristic": "agent"})
            elif "pokechamp_agent" in df.columns:
                df = df.rename(columns={"pokechamp_agent": "agent"})
            
            if "agent" not in df.columns or "opponent" not in df.columns:
                continue
                
            frames.append(df)
        except Exception as exc:
            print(f"⚠️  Could not read {f.name}: {exc}")

    if not frames:
        raise ValueError("No valid data frames could be loaded.")
        
    df = pd.concat(frames, ignore_index=True)
    return df

def _reorder(series: pd.Series, order: list[str]) -> list[str]:
    """Return *order* filtered to only values present in *series*."""
    present = set(series.unique())
    # Ensure they are strings for comparison
    present = {str(x) for x in present} 
    return [x for x in order if x in present] + sorted([x for x in present if x not in order])

def _pivot(df: pd.DataFrame, value: str, agent_order: list[str], opp_order: list[str]) -> pd.DataFrame:
    """Return an agent × opponent pivot for *value*."""
    summary = df.groupby(["agent", "opponent"])[value].mean().reset_index()
    if value == "won":
        summary[value] *= 100  # convert to %
    pivot = summary.pivot(index="agent", columns="opponent", values=value)
    return pivot.reindex(index=agent_order, columns=opp_order)

def save_latex_table(df: pd.DataFrame, path: Path, caption: str, label: str):
    """Save a DataFrame as a LaTeX table."""
    latex = df.to_latex(
        index=True,
        float_format="%.1f",
        caption=caption,
        label=label,
        position="htbp",
        escape=False,
        column_format="l" + "c" * (len(df.columns)),
    )
    latex = latex.replace("\\toprule", "\\hline")
    latex = latex.replace("\\midrule", "\\hline")
    latex = latex.replace("\\bottomrule", "\\hline")
    
    with open(path, "w") as f:
        f.write(latex)
    print(f"📄 LaTeX table saved to: {path}")

# ---------------------------------------------------------------------------
# Report Generator
# ---------------------------------------------------------------------------
def generate_full_report(data_dir: Path, output_dir: Path) -> None:
    """Generate clean individual PNGs and LaTeX tables."""
    apply_premium_style()
    df = load_all_data(data_dir)
    df["win_pct"] = df["won"] * 100.0
    
    # Store display strings
    df["agent_display"] = df["agent"].map(get_display_name)
    df["opponent_display"] = df["opponent"].map(get_display_name)

    # Calculate global orders based on what we actually found
    agents_raw = _reorder(df["agent"], AGENT_ORDER)
    opps_raw = _reorder(df["opponent"], OPPONENT_ORDER)
    
    display_baselines = {get_display_name(x) for x in BASELINES}

    output_dir.mkdir(parents=True, exist_ok=True)
    tex_dir = output_dir / "latex_tables"
    tex_dir.mkdir(parents=True, exist_ok=True)

    # --- 1. Win-Rate Heatmap ---
    fig, ax = plt.subplots(figsize=(12, 9))
    wr_pivot = _pivot(df, "won", agents_raw, opps_raw)
    
    wr_tex = wr_pivot.copy()
    wr_tex.index = [get_display_name(x).replace("_", "\\_") for x in wr_tex.index]
    wr_tex.columns = [get_display_name(x).replace("_", "\\_") for x in wr_tex.columns]
    save_latex_table(wr_tex, tex_dir / "win_rate_matrix.tex", "Matchup Win-Rate Matrix (%)", "tab:win_rate_matrix")

    wr_pivot.index = [get_display_name(x) for x in wr_pivot.index]
    wr_pivot.columns = [get_display_name(x) for x in wr_pivot.columns]
    
    sns.heatmap(
        wr_pivot, annot=True, fmt=".1f", cmap=RD_YL_GN_PREMIUM, 
        vmin=0, vmax=100, linewidths=0.5, linecolor='white', square=False, ax=ax,
        cbar_kws={'shrink': 0.8},
        annot_kws={"size": 9}
    )
    plt.xticks(rotation=45, ha='right')
    finalize_plot(fig)
    plt.savefig(output_dir / "01_win_rate_heatmap.png", bbox_inches='tight', pad_inches=0.01)
    plt.close()

    # --- 2. Overall Agent Ranking ---
    fig, ax = plt.subplots(figsize=(9, min(8, len(agents_raw)*0.4 + 2)))
    ranking_df = df.groupby("agent")["win_pct"].mean().reindex(agents_raw).sort_values(ascending=True)
    display_ranking_labels = [get_display_name(x) for x in ranking_df.index]
    colors = [get_category_color(x) for x in display_ranking_labels]
    
    bars = ax.barh(display_ranking_labels, ranking_df.values, color=colors, alpha=0.9, edgecolor='black', linewidth=0.5)
    ax.axvline(50, color=COLORS["gray"], linestyle=":", alpha=0.5)
    for bar, val in zip(bars, ranking_df.values):
        ax.text(val + 1, bar.get_y() + bar.get_height() / 2, f"{val:.1f}%", va="center", fontsize=8)
    
    ax.set_xlim(0, 105)
    finalize_plot(fig)
    plt.savefig(output_dir / "02_agent_ranking.png", bbox_inches='tight', pad_inches=0.01)
    plt.close()

    # --- 3. Fainted Difference ---
    fig, ax = plt.subplots(figsize=(12, 9))
    f_opp_pivot = _pivot(df, "fainted_opp", agents_raw, opps_raw)
    f_us_pivot = _pivot(df, "fainted_us", agents_raw, opps_raw)
    fainted_diff = f_opp_pivot - f_us_pivot
    
    fd_tex = fainted_diff.copy()
    fd_tex.index = [get_display_name(x).replace("_", "\\_") for x in fd_tex.index]
    fd_tex.columns = [get_display_name(x).replace("_", "\\_") for x in fd_tex.columns]
    save_latex_table(fd_tex, tex_dir / "fainted_diff.tex", "Mean Fainted Pokémon Differential (Opponent - Us)", "tab:fainted_diff")

    fainted_diff.index = [get_display_name(x) for x in fainted_diff.index]
    fainted_diff.columns = [get_display_name(x) for x in fainted_diff.columns]
    
    sns.heatmap(
        fainted_diff, annot=True, fmt=".1f", cmap=RD_YL_GN_PREMIUM, 
        center=0, linewidths=0.5, linecolor='white', square=False, ax=ax,
        cbar_kws={'shrink': 0.8},
        annot_kws={"size": 9}
    )
    plt.xticks(rotation=45, ha='right')
    finalize_plot(fig)
    plt.savefig(output_dir / "03_fainted_diff.png", bbox_inches='tight', pad_inches=0.01)
    plt.close()

    # --- 4. Battle Duration ---
    fig, ax = plt.subplots(figsize=(12, 9))
    turns_pivot = _pivot(df, "turns", agents_raw, opps_raw)
    turns_pivot.index = [get_display_name(x) for x in turns_pivot.index]
    turns_pivot.columns = [get_display_name(x) for x in turns_pivot.columns]
    
    sns.heatmap(
        turns_pivot, annot=True, fmt=".1f", cmap=BLUES_PREMIUM, 
        linewidths=0.5, linecolor='white', square=False, ax=ax,
        cbar_kws={'shrink': 0.8},
        annot_kws={"size": 9}
    )
    plt.xticks(rotation=45, ha='right')
    finalize_plot(fig)
    plt.savefig(output_dir / "04_battle_duration.png", bbox_inches='tight', pad_inches=0.01)
    plt.close()

    # --- 5. Baseline vs Heuristic ---
    fig, ax = plt.subplots(figsize=(10, 6))
    baseline_df = df[df["opponent_display"].isin(display_baselines)].copy()
    heuristic_df = df[~df["opponent_display"].isin(display_baselines)].copy()
    
    baseline_wr = baseline_df.groupby("agent")["win_pct"].mean().reindex(agents_raw).fillna(0)
    heuristic_wr = heuristic_df.groupby("agent")["win_pct"].mean().reindex(agents_raw).fillna(0)
    
    x = np.arange(len(agents_raw))
    width = 0.35
    ax.bar(x - width / 2, baseline_wr.values, width, label="vs Baselines", color=COLORS["primary"], alpha=0.9, edgecolor='black', linewidth=0.5)
    ax.bar(x + width / 2, heuristic_wr.values, width, label="vs Heuristics", color=COLORS["secondary"], alpha=0.9, edgecolor='black', linewidth=0.5)
    
    ax.set_xticks(x)
    ax.set_xticklabels([get_display_name(x) for x in agents_raw], rotation=45, ha="right")
    ax.legend(frameon=True, fontsize=9)
    ax.set_ylabel("Win Rate (%)")
    finalize_plot(fig)
    plt.savefig(output_dir / "05_comparison_baselines.png", bbox_inches='tight', pad_inches=0.01)
    plt.close()

    # --- 6. Efficiency Scatter (Full Spectrum) ---
    fig, ax = plt.subplots(figsize=(11, 9))
    
    agent_summary = (
        df.groupby("agent")
        .agg(avg_turns=("turns", "mean"), avg_win=("win_pct", "mean"))
        .reset_index()
    )
    
    # Re-order based on our global AGENT_ORDER preference if possible
    agent_summary["sort_key"] = agent_summary["agent"].map(lambda x: AGENT_ORDER.index(x) if x in AGENT_ORDER else 99)
    agent_summary = agent_summary.sort_values("sort_key").drop(columns="sort_key")
    
    rng = np.random.default_rng(42)  # Re-seed for consistency
    # Slightly higher jitter to separate dense heuristic clusters (v1-v6)
    agent_summary["jitter_turns"] = agent_summary["avg_turns"] + rng.uniform(-0.15, 0.15, len(agent_summary))
    agent_summary["jitter_win"] = agent_summary["avg_win"] + rng.uniform(-0.6, 0.6, len(agent_summary))
    
    for _, row in agent_summary.iterrows():
        name = get_display_name(row["agent"])
        color = get_category_color(name)
        ax.scatter(row["jitter_turns"], row["jitter_win"], s=180, label=name, color=color, alpha=0.9, edgecolors='black', linewidth=0.6)
        
        # Position annotations with a bit of variety to avoid collisions
        ax.annotate(
            name, (row["jitter_turns"], row["jitter_win"]), 
            xytext=(7, 4), textcoords="offset points", 
            fontsize=9, fontweight="medium"
        )
        
    ax.axhline(50, color='#666', linestyle=":", alpha=0.4)
    ax.set_xlabel("Mean Decision Turns")
    ax.set_ylabel("Mean Success Probability (%)")
    ax.grid(True, linestyle=":", alpha=0.3)
    finalize_plot(fig)
    plt.savefig(output_dir / "06_efficiency_scatter.png", bbox_inches='tight', pad_inches=0.01)
    plt.close()

    # --- 7. Survival Dominance (End-of-Match HP %) ---
    fig, ax = plt.subplots(figsize=(12, 9))
    # Only calculate HP for wins to show 'Dominance'
    win_only_df = df[df["won"] == 1].copy()
    hp_pivot = _pivot(win_only_df, "hp_perc_us", agents_raw, opps_raw)
    hp_pivot.index = [get_display_name(x) for x in hp_pivot.index]
    hp_pivot.columns = [get_display_name(x) for x in hp_pivot.columns]
    
    sns.heatmap(
        hp_pivot, annot=True, fmt=".1f", cmap="YlGn", 
        linewidths=0.5, linecolor='white', ax=ax,
        cbar_kws={'label': 'Mean Winner HP (%)', 'shrink': 0.8}
    )
    plt.xticks(rotation=45, ha='right')
    finalize_plot(fig)
    plt.savefig(output_dir / "07_survival_dominance.png", bbox_inches='tight', pad_inches=0.01)
    plt.close()

    # --- 8. Switching Frequency (Tactical Agility) ---
    fig, ax = plt.subplots(figsize=(10, 6))
    switch_data = df.groupby("agent")["voluntary_switches_us"].mean().reindex(agents_raw).sort_values()
    display_names = [get_display_name(x) for x in switch_data.index]
    colors = [get_category_color(x) for x in display_names]
    
    bars = ax.barh(display_names, switch_data.values, color=colors, alpha=0.85, edgecolor='black', linewidth=0.5)
    for bar, val in zip(bars, switch_data.values):
        ax.text(val + 0.05, bar.get_y() + bar.get_height()/2, f"{val:.2f}", va="center", fontsize=8)
    
    ax.set_xlabel("Mean Voluntary Switches per Battle")
    finalize_plot(fig)
    plt.savefig(output_dir / "08_tactical_agility.png", bbox_inches='tight', pad_inches=0.01)
    plt.close()

    # --- 9. Coverage Effectiveness (Super-Effective Hits) ---
    fig, ax = plt.subplots(figsize=(10, 6))
    # Note: We filter for rows where 'supereffective_us' exists
    if "supereffective_us" in df.columns:
        cov_data = df.groupby("agent")["supereffective_us"].mean().reindex(agents_raw).sort_values()
        display_names = [get_display_name(x) for x in cov_data.index]
        colors = [get_category_color(x) for x in display_names]
        bars = ax.barh(display_names, cov_data.values, color=colors, alpha=0.85, edgecolor='black', linewidth=0.5)
        ax.set_xlabel("Mean Super-Effective Hits per Battle")
        finalize_plot(fig)
        plt.savefig(output_dir / "09_coverage_effectiveness.png", bbox_inches='tight', pad_inches=0.01)
    plt.close()

    # --- 10. Luck Variance (Crits & Misses) ---
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 7))
    
    if "crit_us" in df.columns and "miss_us" in df.columns:
        crit_agg = df.groupby("agent")["crit_us"].mean().reindex(agents_raw)
        miss_agg = df.groupby("agent")["miss_us"].mean().reindex(agents_raw)
        labels = [get_display_name(x) for x in agents_raw]
        
        ax1.bar(labels, crit_agg.values, color=COLORS["primary"], alpha=0.7, label="Critical Hits")
        ax1.set_title("Mean Crit Count")
        ax1.tick_params(axis='x', rotation=45)
        
        ax2.bar(labels, miss_agg.values, color=COLORS["secondary"], alpha=0.7, label="Misses")
        ax2.set_title("Mean Miss Count")
        ax2.tick_params(axis='x', rotation=45)
        
        finalize_plot(fig)
        plt.savefig(output_dir / "10_luck_variance.png", bbox_inches='tight', pad_inches=0.01)
    plt.close()

    # --- 11. Hazard Impact (Side Conditions) ---
    fig, ax = plt.subplots(figsize=(10, 6))
    # Count how many side conditions are typically active
    if "side_conditions_us" in df.columns:
        def count_h(x):
            if pd.isna(x) or x == "": return 0
            return len(str(x).split("|"))
        
        df["hazard_count"] = df["side_conditions_us"].apply(count_h)
        haz_data = df.groupby("agent")["hazard_count"].mean().reindex(agents_raw).sort_values()
        display_names = [get_display_name(x) for x in haz_data.index]
        colors = [get_category_color(x) for x in display_names]
        ax.barh(display_names, haz_data.values, color=colors, alpha=0.85, edgecolor='black', linewidth=0.5)
        ax.set_xlabel("Mean Side Conditions (Hazards/Screens) Active")
        finalize_plot(fig)
        plt.savefig(output_dir / "11_hazard_management.png", bbox_inches='tight', pad_inches=0.01)
    plt.close()

    print(f"✅ Paper export complete. Source: {data_dir.name}")
    print(f"✅ Total battles loaded: {len(df):,}")
    print(f"✅ Agents identified: {df['agent'].unique()}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=str, default=str(DEFAULT_DATA_DIR))
    parser.add_argument("output_dir_pos", nargs="?", help="Optional positional output directory")
    parser.add_argument("--output-dir", type=str, default="src/p01_heuristics/s01_singles/evaluation/results/pokechamp_reports")
    args = parser.parse_args()
    
    output_dir = args.output_dir_pos if args.output_dir_pos else args.output_dir
    generate_full_report(Path(args.data_dir), Path(output_dir))

if __name__ == "__main__":
    main()
