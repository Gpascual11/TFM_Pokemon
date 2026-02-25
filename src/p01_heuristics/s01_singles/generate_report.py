"""Visual Report Generator for Singles Heuristic Benchmarks.

Parses 'benchmark_matrix_summary.csv' to produce a multi-panel visual report
(PNG) containing performance heatmaps, duration charts, and baseline comparisons.
"""

import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import numpy as np


def generate_visual_report(
    csv_path="src/p01_heuristics/s01_singles/results/benchmark_summary.csv",
):
    # 1. Load Data
    try:
        df = pd.read_csv(csv_path)
    except FileNotFoundError:
        print(f"Error: {csv_path} not found. Please run the benchmark first.")
        return

    # Set style
    sns.set_theme(style="whitegrid")
    fig = plt.figure(figsize=(16, 12))

    # 2. Win Rate Heatmap
    plt.subplot(2, 2, 1)
    pivot_wr = df.pivot(index="version", columns="opponent", values="win_rate")
    sns.heatmap(
        pivot_wr, annot=True, fmt=".1f", cmap="RdYlGn", cbar_kws={"label": "Win Rate %"}
    )
    plt.title("Heuristic Performance Heatmap (Win Rate %)")
    plt.xlabel("Opponent")
    plt.ylabel("Heuristic Under Test")

    # 3. Turns Analysis (Efficiency)
    plt.subplot(2, 2, 2)
    avg_turns = df.groupby("version")["avg_turns"].mean().sort_values()
    colors = sns.color_palette("viridis", len(avg_turns))
    avg_turns.plot(kind="bar", color=colors)
    plt.title("Average Battle Duration (Lower = More Efficient)")
    plt.xlabel("Heuristic Version")
    plt.ylabel("Avg Turns per Battle")

    # 4. Success against Baselines
    plt.subplot(2, 2, 3)
    baselines = ["random", "max_power", "simple_heuristic"]
    baseline_df = df[df["opponent"].isin(baselines)]
    sns.barplot(data=baseline_df, x="version", y="win_rate", hue="opponent")
    plt.axhline(50, color="red", linestyle="--", alpha=0.5)
    plt.title("Performance against Baselines")
    plt.ylabel("Win Rate %")

    # 5. Correlation: Turns vs HP Remaining
    plt.subplot(2, 2, 4)
    sns.scatterplot(data=df, x="avg_turns", y="avg_hp_remaining", hue="version", s=100)
    plt.title("Battle Length vs. Survival (HP Remaining)")
    plt.xlabel("Avg Turns")
    plt.ylabel("Avg Remaining HP %")

    plt.tight_layout()
    report_file = "src/p01_heuristics/s01_singles/results/benchmark_report.png"
    plt.savefig(report_file, dpi=300)
    print(f"✅ Analysis report saved as: {report_file}")

    # 6. Print Ranking
    print("\n🏆 HEURISTIC RANKING (Avg. Win Rate against all):")
    ranking = df.groupby("version")["win_rate"].mean().sort_values(ascending=False)
    for i, (ver, val) in enumerate(ranking.items(), 1):
        print(f"{i}. {ver}: {val:.2f}% Win Rate")


if __name__ == "__main__":
    generate_visual_report()
