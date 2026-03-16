"""Per-agent visual report generator for the Pokechamp benchmark.

Loads all per-matchup CSVs for a given Pokechamp agent and produces a multi-panel PNG report.
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

from p01_heuristics.s01_singles.evaluation.reporting.plots.styling import apply_premium_style, finalize_plot, get_display_name, RD_YL_GN_PREMIUM, COLORS, get_category_color

DEFAULT_DATA_DIR = Path("data/1_vs_1/benchmarks/unified")

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def load_agent_data(agent: str, data_dir: Path) -> pd.DataFrame:
    """Load and concatenate all CSVs for *agent* from *data_dir*."""
    pattern = f"pokechamp_{agent}_vs_*.csv"
    files = sorted(data_dir.glob(pattern))
    if not files:
        raise FileNotFoundError(
            f"No CSV files found for agent '{agent}' in '{data_dir}'.\nExpected files matching: {data_dir / pattern}"
        )

    frames = []
    for f in files:
        try:
            frames.append(pd.read_csv(f))
        except Exception as exc:
            print(f"⚠️  Could not read {f.name}: {exc}")

    df = pd.concat(frames, ignore_index=True)
    print(f"✅ Loaded {len(df):,} battles across {len(files)} matchups for '{agent}'.")
    return df

# ---------------------------------------------------------------------------
# Per-matchup summary
# ---------------------------------------------------------------------------
def _summarise(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate battle-level data into per-opponent summary stats."""
    agg = (
        df.groupby("opponent")
        .agg(
            total_games=("won", "count"),
            win_rate=("won", lambda x: x.mean() * 100),
            avg_turns=("turns", "mean"),
            avg_fainted_us=("fainted_us", "mean"),
            avg_fainted_opp=("fainted_opp", "mean"),
            avg_hp_us=("total_hp_us", "mean"),
            avg_hp_opp=("total_hp_opp", "mean"),
        )
        .reset_index()
    )
    return agg

# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
OPPONENT_ORDER = ["v1", "v2", "v3", "v4", "v5", "v6", "random", "max_power", "simple_heuristic"]

def generate_report(agent: str, data_dir: Path, output_dir: Path) -> None:
    """Generate a four-panel PNG report for *agent* with scientific aesthetics."""
    apply_premium_style()
    df = load_agent_data(agent, data_dir)
    summary = _summarise(df)

    # Reorder opponents
    present = [o for o in OPPONENT_ORDER if o in summary["opponent"].values]
    remaining = [o for o in summary["opponent"].values if o not in OPPONENT_ORDER]
    ordered_opponents = present + remaining
    summary["opponent"] = pd.Categorical(summary["opponent"], categories=ordered_opponents, ordered=True)
    summary = summary.sort_values("opponent")

    fig = plt.figure(figsize=(16, 12))
    agent_display = get_display_name(agent)

    # ── Panel 1: Win-rate Heatmap ──────────────────────────────────────────
    ax1 = fig.add_subplot(2, 2, 1)
    wr_matrix = summary.set_index("opponent")[["win_rate"]]
    wr_matrix.index = [get_display_name(x) for x in wr_matrix.index]
    
    sns.heatmap(
        wr_matrix.T, annot=True, fmt=".1f", cmap=RD_YL_GN_PREMIUM, 
        vmin=0, vmax=100, linewidths=0.5, linecolor='#eee', square=True, ax=ax1,
        cbar_kws={"label": "Win Rate %", "orientation": "horizontal", "pad": 0.25}
    )
    ax1.set_title("Table A.1: Success Probability", pad=15)
    ax1.set_xlabel("Adversary")
    ax1.set_yticklabels(["Win %"], rotation=0)

    # ── Panel 2: Battle Duration ─────────────────────────────
    ax2 = fig.add_subplot(2, 2, 2)
    opp_labels = [get_display_name(x) for x in summary["opponent"]]
    colors = [get_category_color(x) for x in opp_labels]
    
    bars = ax2.bar(opp_labels, summary["avg_turns"], color=colors, alpha=0.9, edgecolor='black', linewidth=0.5)
    ax2.set_title("Figure A.1: Battle Length in Turns")
    ax2.set_ylabel("Mean Turns")
    plt.setp(ax2.get_xticklabels(), rotation=45, ha="right")
    
    for bar, val in zip(bars, summary["avg_turns"], strict=False):
        ax2.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.2, f"{val:.1f}", ha="center", fontsize=8)

    # ── Panel 3: Fainted Pokémon comparison ──────────────────────────────
    ax3 = fig.add_subplot(2, 2, 3)
    x = np.arange(len(summary))
    width = 0.35
    ax3.bar(x - width / 2, summary["avg_fainted_us"], width, label=f"Self ({agent})", color=COLORS["danger"], alpha=0.9, edgecolor='black', linewidth=0.5)
    ax3.bar(x + width / 2, summary["avg_fainted_opp"], width, label="Adversary", color=COLORS["success"], alpha=0.9, edgecolor='black', linewidth=0.5)
    
    ax3.set_xticks(x)
    ax3.set_xticklabels(opp_labels, rotation=45, ha="right")
    ax3.set_title("Figure A.2: Fainted Entity Comparison")
    ax3.set_ylabel("Mean Count")
    ax3.legend(frameon=True, fontsize=8)
    ax3.axhline(3, color='#999', linestyle=":", alpha=0.4)

    # ── Panel 4: Surviving HP Scatter ────────────────────────────
    ax4 = fig.add_subplot(2, 2, 4)
    for i, row in summary.iterrows():
        label = opp_labels[i]
        color = colors[i]
        ax4.scatter(row["avg_turns"], row["avg_hp_us"], s=150, color=color, label=label, alpha=0.9, edgecolors='black', linewidth=0.8)
        ax4.annotate(label, (row["avg_turns"], row["avg_hp_us"]), xytext=(5, 5), textcoords="offset points", fontsize=8)

    ax4.set_title("Figure A.3: Trajectory of Health Points")
    ax4.set_xlabel("Mean Turns")
    ax4.set_ylabel("Mean Residual HP")
    ax4.legend(fontsize=7, loc="upper right", ncol=2, frameon=True)

    finalize_plot(
        fig, 
        title=f"Performance Summary: {agent_display}", 
        subtitle=f"Comparative analysis across {len(df):,} discrete battle events"
    )
    
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / f"pokechamp_{agent}_report.png"
    plt.savefig(report_path)
    plt.close()
    print(f"✅ Scientific report saved to: {report_path}")

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> None:
    """Parse arguments and run the report generator."""
    parser = argparse.ArgumentParser(
        description="Generate a visual report from pokechamp benchmark CSVs for a given agent.",
    )
    parser.add_argument(
        "--agent",
        type=str,
        default="random",
        help="Pokechamp agent to analyse (e.g. random, max_power, abyssal, one_step).",
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default=str(DEFAULT_DATA_DIR),
        help="Directory containing per-matchup pokechamp CSVs.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="src/p01_heuristics/s01_singles/evaluation/results/pokechamp_reports",
        help="Directory to save the PNG report.",
    )
    args = parser.parse_args()

    generate_report(
        agent=args.agent,
        data_dir=Path(args.data_dir),
        output_dir=Path(args.output_dir),
    )

if __name__ == "__main__":
    main()
