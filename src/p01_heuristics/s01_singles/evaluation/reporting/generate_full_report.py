"""Full Visual Report Generator for Pokechamp Benchmark Results.

Loads all per-matchup CSVs from ``data/1_vs_1/benchmarks/pokechamp_parallel/`` across
**all** Pokechamp agents and produces a comprehensive multi-panel PNG report:

- Win-rate heatmap (agent × opponent)
- Agent ranking bar chart
- Fainted Pokémon comparison per agent
- Battle duration heatmap (agent × opponent)
- Baseline performance grouped bar chart
- Turn vs HP scatter across all matchups

Run once the full benchmark has completed (all agents, all opponents).

Usage::

    uv run python src/p01_heuristics/s01_singles/evaluation/reporting/generate_full_report.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

# Default location
DEFAULT_DATA_DIR = Path("data/1_vs_1/benchmarks/pokechamp_parallel")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
AGENT_ORDER = [
    "v1",
    "v2",
    "v3",
    "v4",
    "v5",
    "v6",  # (H)
    "random",
    "max_power",
    "simple_heuristic",  # (PE)
    "abyssal",
    "one_step",
    "safe_one_step",
    "pokechamp",
    "pokellmon",  # (PC)
]
OPPONENT_ORDER = [
    "v1",
    "v2",
    "v3",
    "v4",
    "v5",
    "v6",  # (H)
    "random",
    "max_power",
    "simple_heuristic",  # (PE)
    "abyssal",
    "one_step",
    "safe_one_step",  # (PC)
]
BASELINES = {"random", "max_power", "simple_heuristic"}


def get_display_name(name: str) -> str:
    """Add prefixes to differentiate agent types in reports."""
    # poke-env baselines
    if name in {"random", "max_power", "simple_heuristic"}:
        return f"(PE) {name}"
    # heuristics (v1-v6)
    if name.startswith("v") and len(name) > 1 and name[1:].isdigit():
        return f"(H) {name}"
    # Pokechamp agents
    if name in {"abyssal", "one_step", "safe_one_step", "pokechamp", "pokellmon"}:
        return f"(PC) {name}"
    return name


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
            f"No pokechamp CSV files found in '{data_dir}'.\nRun the benchmark first: evaluation/engine/benchmark.py"
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


def _pivot(df: pd.DataFrame, value: str, agent_order: list[str], opp_order: list[str]) -> pd.DataFrame:
    """Return an agent × opponent pivot for *value*."""
    summary = df.groupby(["pokechamp_agent", "opponent"])[value].mean().reset_index()
    if value == "won":
        summary[value] *= 100  # convert to %
    agents = _reorder(summary["pokechamp_agent"], agent_order)
    opps = _reorder(summary["opponent"], opp_order)
    pivot = summary.pivot(index="pokechamp_agent", columns="opponent", values=value)
    return pivot.reindex(index=agents, columns=opps)


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
def generate_full_report(data_dir: Path, output_dir: Path) -> None:
    """Genera informes individuals en format PNG per a cada mètrica."""
    df = load_all_data(data_dir)
    df["win_pct"] = df["won"] * 100.0

    # Aplicar noms de visualització
    df["pokechamp_agent"] = df["pokechamp_agent"].map(get_display_name)
    df["opponent"] = df["opponent"].map(get_display_name)

    display_agents = [get_display_name(x) for x in AGENT_ORDER]
    display_opps = [get_display_name(x) for x in OPPONENT_ORDER]
    display_baselines = {get_display_name(x) for x in BASELINES}

    agents_present = _reorder(df["pokechamp_agent"], display_agents)
    opps_present = _reorder(df["opponent"], display_opps)

    output_dir.mkdir(parents=True, exist_ok=True)
    sns.set_theme(style="whitegrid", font_scale=1.05)

    # --- 1. Win-Rate Heatmap ---
    plt.figure(figsize=(12, 8))
    wr_pivot = _pivot(df, "won", agents_present, opps_present)
    sns.heatmap(wr_pivot, annot=True, fmt=".1f", cmap="RdYlGn", vmin=0, vmax=100, linewidths=0.5)
    plt.title("Win Rate % (Agent × Opponent)")
    plt.tight_layout()
    plt.savefig(output_dir / "01_win_rate_heatmap.png", dpi=200)
    plt.close()

    # --- 2. Overall Agent Ranking ---
    plt.figure(figsize=(10, 8))
    ranking = df.groupby("pokechamp_agent")["win_pct"].mean().reindex(agents_present).sort_values(ascending=True)
    colors = sns.color_palette("RdYlGn", len(ranking))
    bars = plt.barh(ranking.index, ranking.values, color=colors)
    plt.axvline(50, color="gray", linestyle="--", alpha=0.6)
    plt.title("Overall Win Rate by Agent")
    for bar, val in zip(bars, ranking.values):
        plt.text(val + 1, bar.get_y() + bar.get_height() / 2, f"{val:.1f}%", va="center")
    plt.tight_layout()
    plt.savefig(output_dir / "02_agent_ranking.png", dpi=200)
    plt.close()

    # --- 3. Fainted Difference ---
    plt.figure(figsize=(12, 8))
    f_opp_pivot = _pivot(df, "fainted_opp", agents_present, opps_present)
    f_us_pivot = _pivot(df, "fainted_us", agents_present, opps_present)
    fainted_diff = f_opp_pivot - f_us_pivot
    sns.heatmap(fainted_diff, annot=True, fmt=".2f", cmap="RdYlGn", center=0, linewidths=0.5)
    plt.title("Fainted Difference (Opponent - Agent)")
    plt.tight_layout()
    plt.savefig(output_dir / "03_fainted_diff.png", dpi=200)
    plt.close()

    # --- 4. Battle Duration ---
    plt.figure(figsize=(12, 8))
    turns_pivot = _pivot(df, "turns", agents_present, opps_present)
    sns.heatmap(turns_pivot, annot=True, fmt=".1f", cmap="Blues", linewidths=0.5)
    plt.title("Avg Battle Duration (Turns)")
    plt.tight_layout()
    plt.savefig(output_dir / "04_battle_duration.png", dpi=200)
    plt.close()

    # --- 5. Baseline vs Heuristic ---
    plt.figure(figsize=(12, 6))
    baseline_df = df[df["opponent"].isin(display_baselines)].copy()
    heuristic_df = df[~df["opponent"].isin(display_baselines)].copy()
    baseline_wr = baseline_df.groupby("pokechamp_agent")["win_pct"].mean().reindex(agents_present).fillna(0)
    heuristic_wr = heuristic_df.groupby("pokechamp_agent")["win_pct"].mean().reindex(agents_present).fillna(0)
    x = np.arange(len(agents_present))
    width = 0.35
    plt.bar(x - width / 2, baseline_wr.values, width, label="vs Baselines", color="#3498db")
    plt.bar(x + width / 2, heuristic_wr.values, width, label="vs Heuristics", color="#e67e22")
    plt.xticks(x, agents_present, rotation=20, ha="right")
    plt.title("Win Rate: Baselines vs Heuristics")
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_dir / "05_comparison_baselines.png", dpi=200)
    plt.close()

    # --- 6. Efficiency Scatter ---
    plt.figure(figsize=(10, 8))
    agent_summary = (
        df.groupby("pokechamp_agent")
        .agg(avg_turns=("turns", "mean"), avg_win=("win_pct", "mean"))
        .reindex(agents_present)
        .reset_index()
    )
    for _, row in agent_summary.iterrows():
        plt.scatter(row["avg_turns"], row["avg_win"], s=200, label=row["pokechamp_agent"])
        plt.annotate(
            row["pokechamp_agent"], (row["avg_turns"], row["avg_win"]), xytext=(5, 5), textcoords="offset points"
        )
    plt.axhline(50, color="gray", linestyle="--", alpha=0.5)
    plt.title("Efficiency: Battle Length vs Win Rate")
    plt.xlabel("Avg Turns per Battle")
    plt.ylabel("Avg Win Rate %")
    plt.tight_layout()
    plt.savefig(output_dir / "06_efficiency_scatter.png", dpi=200)
    plt.close()

    print(f"✅ S'han guardat 6 informes individuals a: {output_dir}")


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

    generate_full_report(
        data_dir=Path(args.data_dir),
        output_dir=Path(args.output_dir),
    )


if __name__ == "__main__":
    main()
