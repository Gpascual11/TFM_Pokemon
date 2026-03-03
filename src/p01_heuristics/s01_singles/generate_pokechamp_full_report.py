"""Full Visual Report Generator for Pokechamp Benchmark Results.

Loads all per-matchup CSVs from ``data/benchmarks_pokechamp/`` across
**all** Pokechamp agents and produces a comprehensive multi-panel PNG report:

- Win-rate heatmap (agent × opponent)
- Agent ranking bar chart
- Fainted Pokémon comparison per agent
- Battle duration heatmap (agent × opponent)
- Baseline performance grouped bar chart
- Turn vs HP scatter across all matchups

Run once the full benchmark has completed (all agents, all opponents).

Usage::

    uv run python src/p01_heuristics/s01_singles/generate_pokechamp_full_report.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
AGENT_ORDER = ["random", "max_power", "abyssal", "one_step", "pokechamp", "pokellmon"]
OPPONENT_ORDER = ["v1", "v2", "v3", "v4", "v5", "v6", "random", "max_power", "simple_heuristic"]
BASELINES = {"random", "max_power", "simple_heuristic"}


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def load_all_data(data_dir: Path) -> pd.DataFrame:
    """Load and concatenate all per-matchup CSVs found in *data_dir*.

    Parameters
    ----------
    data_dir : Path
        Directory containing ``pokechamp_<agent>_vs_<opponent>.csv`` files.

    Returns
    -------
    pd.DataFrame
        Concatenated battle-level data for all agents and opponents.

    Raises
    ------
    FileNotFoundError
        If no matching CSV files are found.
    """
    files = sorted(data_dir.glob("pokechamp_*_vs_*.csv"))
    if not files:
        raise FileNotFoundError(
            f"No pokechamp CSV files found in '{data_dir}'.\nRun the benchmark first: pokechamp_benchmark.py"
        )

    frames = []
    for f in files:
        try:
            frames.append(pd.read_csv(f))
        except Exception as exc:
            print(f"⚠️  Could not read {f.name}: {exc}")

    df = pd.concat(frames, ignore_index=True)
    agents = df["pokechamp_agent"].nunique()
    opps = df["opponent"].nunique()
    print(f"✅ Loaded {len(df):,} battles — {agents} agents × {opps} opponents.")
    return df


# ---------------------------------------------------------------------------
# Aggregation helpers
# ---------------------------------------------------------------------------
def _reorder(series: pd.Categorical, order: list[str]) -> list[str]:
    """Return *order* filtered to only values present in *series*."""
    present = set(series.unique())
    return [x for x in order if x in present] + [x for x in present if x not in order]


def _pivot(df: pd.DataFrame, value: str) -> pd.DataFrame:
    """Return an agent × opponent pivot for *value*."""
    summary = df.groupby(["pokechamp_agent", "opponent"])[value].mean().reset_index()
    if value == "won":
        summary[value] *= 100  # convert to %
    agents = _reorder(summary["pokechamp_agent"], AGENT_ORDER)
    opps = _reorder(summary["opponent"], OPPONENT_ORDER)
    pivot = summary.pivot(index="pokechamp_agent", columns="opponent", values=value)
    return pivot.reindex(index=agents, columns=opps)


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
def generate_full_report(data_dir: Path, output_dir: Path) -> None:
    """Generate a six-panel PNG report across all Pokechamp agents.

    Parameters
    ----------
    data_dir : Path
        Directory containing per-matchup CSVs.
    output_dir : Path
        Directory where the PNG report is saved.
    """
    df = load_all_data(data_dir)
    df["win_pct"] = df["won"] * 100.0

    agents_present = _reorder(df["pokechamp_agent"], AGENT_ORDER)
    opps_present = _reorder(df["opponent"], OPPONENT_ORDER)

    sns.set_theme(style="whitegrid", font_scale=1.05)
    fig = plt.figure(figsize=(22, 18))
    fig.suptitle(
        f"Pokechamp Full Benchmark Report — {len(agents_present)} agents × {len(opps_present)} opponents",
        fontsize=17,
        fontweight="bold",
        y=1.005,
    )

    # ── Panel 1: Win-Rate Heatmap ──────────────────────────────────────────
    ax1 = fig.add_subplot(3, 2, 1)
    wr_pivot = _pivot(df, "won")
    sns.heatmap(
        wr_pivot,
        annot=True,
        fmt=".1f",
        cmap="RdYlGn",
        vmin=0,
        vmax=100,
        linewidths=0.5,
        cbar_kws={"label": "Win Rate %"},
        ax=ax1,
    )
    ax1.set_title("Win Rate % (Agent × Opponent)")
    ax1.set_xlabel("Opponent")
    ax1.set_ylabel("Pokechamp Agent")
    ax1.tick_params(axis="x", rotation=30)

    # ── Panel 2: Overall Agent Ranking ────────────────────────────────────
    ax2 = fig.add_subplot(3, 2, 2)
    ranking = df.groupby("pokechamp_agent")["win_pct"].mean().reindex(agents_present).sort_values(ascending=True)
    colors = sns.color_palette("RdYlGn", len(ranking))
    bars = ax2.barh(ranking.index, ranking.values, color=colors)
    ax2.axvline(50, color="gray", linestyle="--", alpha=0.6)
    ax2.set_title("Overall Win Rate by Agent (avg over all opponents)")
    ax2.set_xlabel("Avg Win Rate %")
    ax2.set_xlim(0, 100)
    for bar, val in zip(bars, ranking.values, strict=False):
        ax2.text(val + 1, bar.get_y() + bar.get_height() / 2, f"{val:.1f}%", va="center", fontsize=9)

    # ── Panel 3: Avg Fainted Us vs Opp heatmap ────────────────────────────
    ax3 = fig.add_subplot(3, 2, 3)
    fainted_diff = _pivot(df, "fainted_opp") - _pivot(df, "fainted_us")
    sns.heatmap(
        fainted_diff,
        annot=True,
        fmt=".2f",
        cmap="RdYlGn",
        center=0,
        linewidths=0.5,
        cbar_kws={"label": "Fainted diff (opp − us)"},
        ax=ax3,
    )
    ax3.set_title("Fainted Difference: Opponent − Agent\n(green = agent faints more opponents)")
    ax3.set_xlabel("Opponent")
    ax3.set_ylabel("Pokechamp Agent")
    ax3.tick_params(axis="x", rotation=30)

    # ── Panel 4: Avg Battle Duration Heatmap ─────────────────────────────
    ax4 = fig.add_subplot(3, 2, 4)
    turns_pivot = _pivot(df, "turns")
    sns.heatmap(
        turns_pivot,
        annot=True,
        fmt=".1f",
        cmap="Blues",
        linewidths=0.5,
        cbar_kws={"label": "Avg Turns"},
        ax=ax4,
    )
    ax4.set_title("Avg Battle Duration (Turns)")
    ax4.set_xlabel("Opponent")
    ax4.set_ylabel("Pokechamp Agent")
    ax4.tick_params(axis="x", rotation=30)

    # ── Panel 5: Baseline vs Heuristic Comparison ─────────────────────────
    ax5 = fig.add_subplot(3, 2, 5)
    baseline_df = df[df["opponent"].isin(BASELINES)].copy()
    heuristic_df = df[~df["opponent"].isin(BASELINES)].copy()
    baseline_wr = baseline_df.groupby("pokechamp_agent")["win_pct"].mean().reindex(agents_present)
    heuristic_wr = heuristic_df.groupby("pokechamp_agent")["win_pct"].mean().reindex(agents_present)
    x = np.arange(len(agents_present))
    width = 0.35
    ax5.bar(x - width / 2, baseline_wr.values, width, label="vs Baselines", color="#3498db", alpha=0.85)
    ax5.bar(x + width / 2, heuristic_wr.values, width, label="vs Heuristics (v1–v6)", color="#e67e22", alpha=0.85)
    ax5.set_xticks(x)
    ax5.set_xticklabels(agents_present, rotation=20, ha="right")
    ax5.axhline(50, color="gray", linestyle="--", alpha=0.5)
    ax5.set_title("Win Rate: vs Baselines vs vs Heuristics")
    ax5.set_ylabel("Win Rate %")
    ax5.set_ylim(0, 100)
    ax5.legend()

    # ── Panel 6: Avg Turns vs Avg Win Rate Scatter ────────────────────────
    ax6 = fig.add_subplot(3, 2, 6)
    agent_summary = (
        df.groupby("pokechamp_agent")
        .agg(avg_turns=("turns", "mean"), avg_win=("win_pct", "mean"))
        .reindex(agents_present)
        .reset_index()
    )
    scatter_palette = sns.color_palette("tab10", len(agent_summary))
    for (_, row), color in zip(agent_summary.iterrows(), scatter_palette, strict=False):
        ax6.scatter(row["avg_turns"], row["avg_win"], s=250, color=color, zorder=3, label=row["pokechamp_agent"])
        ax6.annotate(
            row["pokechamp_agent"],
            (row["avg_turns"], row["avg_win"]),
            textcoords="offset points",
            xytext=(7, 5),
            fontsize=9,
        )
    ax6.axhline(50, color="gray", linestyle="--", alpha=0.5)
    ax6.set_title("Efficiency: Avg Battle Length vs Win Rate")
    ax6.set_xlabel("Avg Turns per Battle")
    ax6.set_ylabel("Avg Win Rate %")
    ax6.legend(fontsize=8, loc="upper right")

    plt.tight_layout()
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "pokechamp_full_report.png"
    plt.savefig(report_path, dpi=200, bbox_inches="tight")
    plt.close()
    print(f"✅ Full report saved to: {report_path}")

    # ── Terminal summary ──────────────────────────────────────────────────
    print("\n🏆 AGENT RANKING (avg win rate over all opponents):")
    ranked = df.groupby("pokechamp_agent")["win_pct"].mean().sort_values(ascending=False)
    for i, (agent, wr) in enumerate(ranked.items(), 1):
        bar = "█" * int(wr / 5)
        print(f"  {i}. {agent:<18} {wr:5.1f}%  {bar}")

    print(f"\n📊 OVERALL STATS ({len(df):,} battles):")
    print(f"  Global win rate:   {df['won'].mean() * 100:.1f}%")
    print(f"  Avg turns:         {df['turns'].mean():.1f}")
    print(f"  Avg fainted (us):  {df['fainted_us'].mean():.2f}")
    print(f"  Avg fainted (opp): {df['fainted_opp'].mean():.2f}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> None:
    """Parse arguments and run the full report generator."""
    parser = argparse.ArgumentParser(
        description="Generate a full cross-agent report from all pokechamp benchmark CSVs.",
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default="data/benchmarks_pokechamp",
        help="Directory containing per-matchup pokechamp CSVs.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="src/p01_heuristics/s01_singles/results",
        help="Directory to save the PNG report.",
    )
    args = parser.parse_args()

    generate_full_report(
        data_dir=Path(args.data_dir),
        output_dir=Path(args.output_dir),
    )


if __name__ == "__main__":
    main()
