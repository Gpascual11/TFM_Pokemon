"""Visual Report Generator for Singles Heuristic Benchmarks.

Parses the ``benchmark_summary.csv`` produced by ``benchmark.py`` and
generates a multi-panel PNG containing performance heatmaps, duration
charts, and baseline comparisons.

Usage::

    uv run python src/p01_heuristics/s01_singles/heuristics/generate_report.py
"""

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns


def generate_visual_report(
    csv_path: str = "src/p01_heuristics/s01_singles/heuristics/results/benchmark_summary.csv",
) -> None:
    """Load *csv_path* and save a four-panel PNG report to ``results/``.

    Parameters
    ----------
    csv_path : str
        Path to the summary CSV produced by ``benchmark.py``.
    """
    try:
        df = pd.read_csv(csv_path)
    except FileNotFoundError:
        print(f"Error: '{csv_path}' not found. Run benchmark.py first.")
        return

    sns.set_theme(style="whitegrid")
    plt.figure(figsize=(16, 12))

    # ── Panel 1: Win-Rate Heatmap ──────────────────────────────────────────
    plt.subplot(2, 2, 1)
    pivot_wr = df.pivot(index="version", columns="opponent", values="win_rate")
    sns.heatmap(pivot_wr, annot=True, fmt=".1f", cmap="RdYlGn", cbar_kws={"label": "Win Rate %"})
    plt.title("Heuristic Performance Heatmap (Win Rate %)")
    plt.xlabel("Opponent")
    plt.ylabel("Heuristic Under Test")

    # ── Panel 2: Battle Duration ───────────────────────────────────────────
    plt.subplot(2, 2, 2)
    avg_turns = df.groupby("version")["avg_turns"].mean().sort_values()
    colors = sns.color_palette("viridis", len(avg_turns))
    avg_turns.plot(kind="bar", color=colors)
    plt.title("Average Battle Duration (Lower = More Efficient)")
    plt.xlabel("Heuristic Version")
    plt.ylabel("Avg Turns per Battle")

    # ── Panel 3: Baseline Performance ─────────────────────────────────────
    plt.subplot(2, 2, 3)
    baselines = ["random", "max_power", "simple_heuristic"]
    baseline_df = df[df["opponent"].isin(baselines)]
    sns.barplot(data=baseline_df, x="version", y="win_rate", hue="opponent")
    plt.axhline(50, color="red", linestyle="--", alpha=0.5)
    plt.title("Performance against Baselines")
    plt.ylabel("Win Rate %")

    # ── Panel 4: Turns vs HP Remaining ────────────────────────────────────
    plt.subplot(2, 2, 4)
    sns.scatterplot(data=df, x="avg_turns", y="avg_hp_remaining", hue="version", s=100)
    plt.title("Battle Length vs. Survival (HP Remaining)")
    plt.xlabel("Avg Turns")
    plt.ylabel("Avg Remaining HP %")

    plt.tight_layout()
    report_file = "src/p01_heuristics/s01_singles/heuristics/results/benchmark_report.png"
    plt.savefig(report_file, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"✅ Analysis report saved as: {report_file}")

    # ── Terminal ranking ───────────────────────────────────────────────────
    print("\n🏆 HEURISTIC RANKING (Avg. Win Rate against all):")
    ranking = df.groupby("version")["win_rate"].mean().sort_values(ascending=False)
    for i, (ver, val) in enumerate(ranking.items(), 1):
        print(f"  {i}. {ver}: {val:.2f}% Win Rate")


if __name__ == "__main__":
    generate_visual_report()
