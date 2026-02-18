"""
Analysis utilities to compare two doubles (2-vs-2) heuristic runs.

Each CSV should be produced by the updated v1/v2 scripts and contain:
- battle_id, winner, turns, won
- team_us, team_opp
- fainted_us, fainted_opp
- moves_used (pipe-separated move ids).
"""

from __future__ import annotations

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


def _compute_summary(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute per-heuristic summary stats for doubles battles.

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
        n = len(turns)
        mean_t = turns.mean()
        sd_t = turns.std(ddof=1)
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


def _explode_pipe_column(
    df: pd.DataFrame, col: str, value_name: str
) -> pd.DataFrame:
    """
    Expand a pipe-separated column into long form.

    Example:
    - col = 'moves_used', value_name='move_id'
    - col = 'team_us', value_name='species'
    """
    rows = []
    for _, row in df.iterrows():
        heuristic = row["heuristic"]
        raw_val = row.get(col, "")
        # Treat NaN / missing as empty (no tokens)
        if pd.isna(raw_val):
            continue
        raw = str(raw_val).strip()
        if not raw:
            continue
        for token in raw.split("|"):
            token = token.strip()
            if not token:
                continue
            rows.append({"heuristic": heuristic, value_name: token})
    if not rows:
        return pd.DataFrame(columns=["heuristic", value_name, "count"])
    long_df = pd.DataFrame(rows)
    counts = (
        long_df.groupby(["heuristic", value_name])
        .size()
        .reset_index(name="count")
        .sort_values(["heuristic", "count"], ascending=[True, False])
    )
    return counts


def _plot_turn_distribution(df: pd.DataFrame, out_dir: Path) -> None:
    """Plot KDE+hist of battle duration for the two doubles heuristics."""
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
    plt.title("Doubles Battle Duration Distribution per Heuristic")
    plt.xlabel("Number of Turns")
    plt.ylabel("Density")
    plt.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    (out_dir / "turn_distribution_doubles.png").parent.mkdir(
        parents=True, exist_ok=True
    )
    plt.savefig(out_dir / "turn_distribution_doubles.png")
    plt.close()


def _plot_boxplot_turns(df: pd.DataFrame, out_dir: Path) -> None:
    """Boxplot of turns per heuristic for doubles."""
    plt.figure(figsize=(8, 6))
    sns.boxplot(data=df, x="heuristic", y="turns", palette="Set2")
    plt.title("Doubles Battle Length (Turns) per Heuristic")
    plt.xlabel("Heuristic")
    plt.ylabel("Turns")
    plt.tight_layout()
    plt.savefig(out_dir / "turn_boxplot_doubles.png")
    plt.close()


def _plot_win_rates(summary: pd.DataFrame, out_dir: Path) -> None:
    """Barplot of doubles win rates per heuristic."""
    plt.figure(figsize=(6, 4))
    ax = sns.barplot(
        data=summary, x="heuristic", y="win_rate_%", palette="viridis"
    )
    ax.set_ylabel("Win rate (%)")
    ax.set_xlabel("Heuristic")
    ax.set_title("Doubles Win Rate per Heuristic")
    for p in ax.patches:
        h = p.get_height()
        ax.annotate(
            f"{h:.2f}%",
            (p.get_x() + p.get_width() / 2.0, h),
            ha="center",
            va="bottom",
            fontsize=9,
        )
    plt.tight_layout()
    plt.savefig(out_dir / "win_rates_doubles.png")
    plt.close()


def _plot_top_moves(moves_counts: pd.DataFrame, out_dir: Path, top_k: int = 15) -> None:
    """Top-k moves used per heuristic in doubles."""
    if moves_counts.empty:
        return
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
        data=top_df, x="move_id", y="count", hue="heuristic", palette="viridis"
    )
    plt.xticks(rotation=45, ha="right")
    plt.title(f"Top {top_k} Moves Used per Heuristic (Doubles)")
    plt.xlabel("Move ID")
    plt.ylabel("Usage Count")
    plt.tight_layout()
    plt.savefig(out_dir / "top_moves_doubles.png")
    plt.close()


def _plot_top_species(species_counts: pd.DataFrame, out_dir: Path, top_k: int = 15) -> None:
    """Top-k Pokémon species appearing on our side per heuristic."""
    if species_counts.empty:
        return
    totals = (
        species_counts.groupby("species")["count"]
        .sum()
        .sort_values(ascending=False)
        .head(top_k)
    )
    top_ids = set(totals.index)
    top_df = species_counts[species_counts["species"].isin(top_ids)].copy()

    plt.figure(figsize=(12, 6))
    sns.barplot(
        data=top_df,
        x="species",
        y="count",
        hue="heuristic",
        palette="magma",
    )
    plt.xticks(rotation=45, ha="right")
    plt.title(f"Top {top_k} Pokémon Used per Heuristic (Doubles, Our Side)")
    plt.xlabel("Species")
    plt.ylabel("Appearance Count")
    plt.tight_layout()
    plt.savefig(out_dir / "top_species_doubles.png")
    plt.close()


def compare_doubles_heuristics(
    csv_a: str | Path,
    csv_b: str | Path,
    label_a: str | None = None,
    label_b: str | None = None,
    output_dir: str | Path = "data/heuristics_doubles_compare",
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Compare two doubles (2v2) heuristic runs and generate plots + summary tables.

    :param csv_a: Path to the first CSV.
    :param csv_b: Path to the second CSV.
    :param label_a: Optional label for the first heuristic (default: stem of csv_a).
    :param label_b: Optional label for the second heuristic (default: stem of csv_b).
    :param output_dir: Directory where plots will be saved.

    :return: (summary_stats, move_usage_counts, species_usage_counts)
    """
    csv_a = Path(csv_a)
    csv_b = Path(csv_b)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    label_a = label_a or csv_a.stem
    label_b = label_b or csv_b.stem

    df_a = _load_with_label(csv_a, label_a)
    df_b = _load_with_label(csv_b, label_b)
    df_all = pd.concat([df_a, df_b], ignore_index=True)

    summary = _compute_summary(df_all)

    moves_counts = _explode_pipe_column(df_all, "moves_used", "move_id")
    species_counts = _explode_pipe_column(df_all, "team_us", "species")

    _plot_turn_distribution(df_all, out_dir)
    _plot_boxplot_turns(df_all, out_dir)
    _plot_win_rates(summary, out_dir)
    _plot_top_moves(moves_counts, out_dir)
    _plot_top_species(species_counts, out_dir)

    return summary, moves_counts, species_counts


__all__ = ["compare_doubles_heuristics"]

