"""Per-agent visual report generator for the Pokechamp benchmark.

Loads all per-matchup CSVs for a given Pokechamp agent from
``data/1_vs_1/benchmarks/pokechamp/`` and produces a multi-panel PNG report with:

- Win-rate heatmap (agent vs each opponent)
- Average battle duration per opponent
- Fainted Pokémon comparison (us vs opponent)
- HP remaining scatter (turns vs surviving HP)

Usage::

    # Analyse the 'random' agent (default)
    uv run python src/p01_heuristics/s01_singles/evaluation/reporting/generate_report.py

    # Analyse a specific agent
    uv run python src/p01_heuristics/s01_singles/evaluation/reporting/generate_report.py --agent max_power

    # Use a custom data directory
    uv run python src/p01_heuristics/s01_singles/evaluation/reporting/generate_report.py \\
        --agent abyssal --data-dir data/1_vs_1/benchmarks/pokechamp
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

DEFAULT_DATA_DIR = Path("data/1_vs_1/benchmarks/pokechamp")


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def load_agent_data(agent: str, data_dir: Path) -> pd.DataFrame:
    """Load and concatenate all CSVs for *agent* from *data_dir*.

    Parameters
    ----------
    agent : str
        Pokechamp agent identifier (e.g. ``"random"``, ``"abyssal"``).
    data_dir : Path
        Directory containing per-matchup CSV files.

    Returns
    -------
    pd.DataFrame
        Concatenated battle-level data for the requested agent.

    Raises
    ------
    FileNotFoundError
        If no CSV files are found for *agent* in *data_dir*.
    """
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
    """Generate a four-panel PNG report for *agent*.

    Parameters
    ----------
    agent : str
        Pokechamp agent to analyse.
    data_dir : Path
        Directory with per-matchup CSVs.
    output_dir : Path
        Directory where the PNG report is saved.
    """
    df = load_agent_data(agent, data_dir)
    summary = _summarise(df)

    # Reorder opponents to a canonical order (keep only those present).
    present = [o for o in OPPONENT_ORDER if o in summary["opponent"].values]
    remaining = [o for o in summary["opponent"].values if o not in OPPONENT_ORDER]
    ordered_opponents = present + remaining
    summary["opponent"] = pd.Categorical(summary["opponent"], categories=ordered_opponents, ordered=True)
    summary = summary.sort_values("opponent")

    sns.set_theme(style="whitegrid", font_scale=1.1)
    fig = plt.figure(figsize=(18, 13))
    fig.suptitle(
        f"Pokechamp Agent Report — '{agent}' ({len(df):,} battles total)",
        fontsize=16,
        fontweight="bold",
        y=1.01,
    )

    # ── Panel 1: Win-rate heatmap ──────────────────────────────────────────
    ax1 = fig.add_subplot(2, 2, 1)
    wr_matrix = summary.set_index("opponent")[["win_rate"]]
    sns.heatmap(
        wr_matrix.T,
        annot=True,
        fmt=".1f",
        cmap="RdYlGn",
        vmin=0,
        vmax=100,
        linewidths=0.5,
        cbar_kws={"label": "Win Rate %"},
        ax=ax1,
    )
    ax1.set_title(f"Win Rate % — '{agent}' vs each opponent")
    ax1.set_xlabel("Opponent")
    ax1.set_ylabel("")
    ax1.set_yticklabels(["Win Rate"], rotation=0)

    # ── Panel 2: Battle duration per opponent ─────────────────────────────
    ax2 = fig.add_subplot(2, 2, 2)
    palette = sns.color_palette("viridis", len(summary))
    ax2.bar(summary["opponent"], summary["avg_turns"], color=palette)
    ax2.set_title("Avg Battle Duration per Opponent")
    ax2.set_xlabel("Opponent")
    ax2.set_ylabel("Avg Turns")
    ax2.tick_params(axis="x", rotation=30)
    for bar, val in zip(ax2.patches, summary["avg_turns"], strict=False):
        ax2.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.3,
            f"{val:.1f}",
            ha="center",
            va="bottom",
            fontsize=9,
        )

    # ── Panel 3: Fainted Pokémon comparison ──────────────────────────────
    ax3 = fig.add_subplot(2, 2, 3)
    x = np.arange(len(summary))
    width = 0.35
    ax3.bar(x - width / 2, summary["avg_fainted_us"], width, label=f"'{agent}' fainted", color="#e74c3c", alpha=0.85)
    ax3.bar(x + width / 2, summary["avg_fainted_opp"], width, label="Opponent fainted", color="#2ecc71", alpha=0.85)
    ax3.set_xticks(x)
    ax3.set_xticklabels(summary["opponent"], rotation=30, ha="right")
    ax3.set_title("Avg Fainted Pokémon per Battle")
    ax3.set_ylabel("Avg Fainted")
    ax3.legend()
    ax3.axhline(3, color="gray", linestyle="--", alpha=0.4, linewidth=0.8)

    # ── Panel 4: Turns vs HP remaining scatter ────────────────────────────
    ax4 = fig.add_subplot(2, 2, 4)
    scatter_palette = sns.color_palette("tab10", len(summary))
    for (_, row), color in zip(summary.iterrows(), scatter_palette, strict=False):
        ax4.scatter(
            row["avg_turns"],
            row["avg_hp_us"],
            s=200,
            color=color,
            label=row["opponent"],
            zorder=3,
        )
        ax4.annotate(
            row["opponent"],
            (row["avg_turns"], row["avg_hp_us"]),
            textcoords="offset points",
            xytext=(6, 4),
            fontsize=8,
        )
    ax4.set_title(f"Battle Length vs Surviving HP — '{agent}'")
    ax4.set_xlabel("Avg Turns")
    ax4.set_ylabel(f"Avg Remaining HP ({agent})")
    ax4.legend(fontsize=7, loc="upper right", ncol=2)

    plt.tight_layout()
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / f"pokechamp_{agent}_report.png"
    plt.savefig(report_path, dpi=200, bbox_inches="tight")
    plt.close()
    print(f"✅ Report saved to: {report_path}")

    # ── Terminal ranking ──────────────────────────────────────────────────
    print(f"\n🏆 WIN RATE RANKING — '{agent}' vs opponents:")
    ranked = summary.sort_values("win_rate", ascending=False)
    for i, row in enumerate(ranked.itertuples(), 1):
        bar = "█" * int(row.win_rate / 5)
        print(f"  {i:2}. {row.opponent:<18} {row.win_rate:5.1f}%  {bar}")

    print("\n📊 SUMMARY STATS:")
    print(f"  Total battles:     {len(df):,}")
    print(f"  Overall win rate:  {df['won'].mean() * 100:.1f}%")
    print(f"  Avg turns:         {df['turns'].mean():.1f}")
    print(f"  Avg fainted (us):  {df['fainted_us'].mean():.2f}")
    print(f"  Avg fainted (opp): {df['fainted_opp'].mean():.2f}")


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
