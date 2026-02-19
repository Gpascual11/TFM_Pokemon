"""
Analysis utilities to compare two singles (1-vs-1) heuristic runs.

Given two CSVs produced by `test_heuristic_v5.py`, this module:
- computes basic statistics (mean turns, win rates, counts),
- generates several comparison plots,
- inspects which Pokémon and moves appear most frequently.

Usage (from a notebook or script):

    from testing_heuristics.analysis_singles_heuristics import compare_singles_heuristics

    summary = compare_singles_heuristics(
        csv_a=\"../data/tfm_expert_singles_runA.csv\",
        csv_b=\"../data/tfm_expert_singles_runB.csv\",
        label_a=\"Heuristic A\",
        label_b=\"Heuristic B\",
        output_dir=\"../data/heuristics_compare_A_vs_B\",
    )

"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy import stats


def _load_with_label(path: str | Path, label: str) -> pd.DataFrame:
    """Load a CSV and attach a `heuristic` label column."""
    df = pd.read_csv(path)
    df["heuristic"] = label
    return df


def _ensure_output_dir(output_dir: str | Path) -> Path:
    """Ensure the output directory exists and return it as a Path."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    return out


def _compute_summary(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute per-heuristic summary stats for turns and win rate.

    Returns a DataFrame with:
    - heuristic
    - battles
    - mean_turns, sd_turns
    - 95% CI for mean turns
    - win_rate_%
    """
    rows = []
    for hname, g in df.groupby("heuristic"):
        turns = g["turns"].to_numpy()
        mean_t = turns.mean()
        sd_t = turns.std(ddof=1)
        n = len(turns)
        ci_low, ci_high = stats.t.interval(
            0.95, n - 1, loc=mean_t, scale=stats.sem(turns)
        )
        win_rate = 100.0 * g["won"].mean()
        rows.append(
            {
                "heuristic": hname,
                "battles": n,
                "mean_turns": round(mean_t, 2),
                "sd_turns": round(sd_t, 2),
                "ci_turns": f"[{ci_low:.2f}, {ci_high:.2f}]",
                "win_rate_%": round(win_rate, 2),
            }
        )
    return pd.DataFrame(rows)


def _explode_moves(df: pd.DataFrame) -> pd.DataFrame:
    """
    Expand the `moves_used` pipe-separated column into a long-form table.

    Returns a DataFrame with columns:
    - heuristic
    - move_id
    - count

    Empty / missing values in `moves_used` are ignored.
    """
    rows = []
    for _, row in df.iterrows():
        heuristic = row["heuristic"]
        moves_str = str(row.get("moves_used", "") or "")
        if not moves_str:
            continue
        for mid in moves_str.split("|"):
            mid = mid.strip()
            if not mid:
                continue
            rows.append({"heuristic": heuristic, "move_id": mid})

    if not rows:
        return pd.DataFrame(columns=["heuristic", "move_id", "count"])

    long_df = pd.DataFrame(rows)
    counts = (
        long_df.groupby(["heuristic", "move_id"])
        .size()
        .reset_index(name="count")
        .sort_values(["heuristic", "count"], ascending=[True, False])
    )
    return counts


def _plot_turn_distribution(df: pd.DataFrame, output_dir: Path) -> None:
    """Plot and save a KDE + histogram of battle turns per heuristic."""
    plt.figure(figsize=(10, 6))
    sns.histplot(
        data=df,
        x="turns",
        hue="heuristic",
        kde=True,
        element="step",
        stat="density",
        common_norm=False,
        palette="viridis",
    )
    plt.title("Battle Duration Distribution per Heuristic")
    plt.xlabel("Number of Turns")
    plt.ylabel("Density")
    plt.grid(axis="y", alpha=0.3)

    out = output_dir / "turn_distribution.png"
    plt.tight_layout()
    plt.savefig(out)
    plt.close()


def _plot_boxplot_turns(df: pd.DataFrame, output_dir: Path) -> None:
    """Boxplot of number of turns per heuristic."""
    plt.figure(figsize=(8, 6))
    sns.boxplot(data=df, x="heuristic", y="turns", palette="Set2")
    plt.title("Distribution of Battle Length (Turns) per Heuristic")
    plt.xlabel("Heuristic")
    plt.ylabel("Turns")

    out = output_dir / "turn_boxplot.png"
    plt.tight_layout()
    plt.savefig(out)
    plt.close()


def _plot_win_rates(summary: pd.DataFrame, output_dir: Path) -> None:
    """Barplot of win rate per heuristic."""
    plt.figure(figsize=(6, 4))
    ax = sns.barplot(
        data=summary, x="heuristic", y="win_rate_%", palette="viridis"
    )
    ax.set_ylabel("Win rate (%)")
    ax.set_xlabel("Heuristic")
    ax.set_title("Win Rate per Heuristic")
    for p in ax.patches:
        height = p.get_height()
        ax.annotate(
            f"{height:.2f}%",
            (p.get_x() + p.get_width() / 2.0, height),
            ha="center",
            va="bottom",
            fontsize=9,
        )
    out = output_dir / "win_rates.png"
    plt.tight_layout()
    plt.savefig(out)
    plt.close()


def _plot_top_moves(moves_counts: pd.DataFrame, output_dir: Path, top_k: int = 15) -> None:
    """
    Plot the top-k most frequently used moves across both heuristics.

    The plot shows counts per heuristic for each move id.
    """
    if moves_counts.empty:
        return

    # Pick global top-k by total count
    totals = (
        moves_counts.groupby("move_id")["count"]
        .sum()
        .sort_values(ascending=False)
        .head(top_k)
    )
    top_ids = set(totals.index)
    top_df = moves_counts[moves_counts["move_id"].isin(top_ids)].copy()

    plt.figure(figsize=(12, 6))
    sns.barplot(
        data=top_df,
        x="move_id",
        y="count",
        hue="heuristic",
        palette="viridis",
    )
    plt.xticks(rotation=45, ha="right")
    plt.title(f"Top {top_k} Moves Used by Each Heuristic")
    plt.xlabel("Move ID")
    plt.ylabel("Usage Count")
    plt.tight_layout()
    out = output_dir / "top_moves.png"
    plt.savefig(out)
    plt.close()


def compare_singles_heuristics(
    csv_a: str | Path,
    csv_b: str | Path,
    label_a: str | None = None,
    label_b: str | None = None,
    output_dir: str | Path = "data/heuristics_compare",
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Compare two singles heuristic runs and generate plots + summary tables.

    :param csv_a: Path to the first CSV (output of `test_heuristic_v5.py`).
    :param csv_b: Path to the second CSV.
    :param label_a: Optional display label for the first heuristic. Defaults to the stem.
    :param label_b: Optional display label for the second heuristic. Defaults to the stem.
    :param output_dir: Directory where all plots will be saved.

    :return: (summary_stats, move_usage_counts)
        - summary_stats: DataFrame with high-level metrics per heuristic.
        - move_usage_counts: long-form table of move usage counts.
    """
    csv_a = Path(csv_a)
    csv_b = Path(csv_b)

    label_a = label_a or csv_a.stem
    label_b = label_b or csv_b.stem

    df_a = _load_with_label(csv_a, label_a)
    df_b = _load_with_label(csv_b, label_b)
    df_all = pd.concat([df_a, df_b], ignore_index=True)

    out_dir = _ensure_output_dir(output_dir)

    # Summary metrics
    summary = _compute_summary(df_all)

    # Move usage breakdown
    moves_counts = _explode_moves(df_all)

    # Plots
    _plot_turn_distribution(df_all, out_dir)
    _plot_boxplot_turns(df_all, out_dir)
    _plot_win_rates(summary, out_dir)
    _plot_top_moves(moves_counts, out_dir)

    return summary, moves_counts


__all__ = ["compare_singles_heuristics"]

