"""Visual Report Generator for RL Model Benchmarks.

Parses 'benchmark_rl_summary.csv' to produce a multi-panel visual report
containing performance heatmaps, duration charts, and baseline comparisons.
"""

import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from pathlib import Path


def generate_visual_report(
    csv_path="src/p04_rl_models/s03_evaluation/results/benchmark_rl_summary.csv",
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

    # Order versions if possible
    version_order = ["B", "P15", "P2", "P3"]
    existing_versions = [v for v in version_order if v in df["version"].unique()]

    # 2. Win Rate Heatmap
    plt.subplot(2, 2, 1)
    pivot_wr = df.pivot(index="version", columns="opponent", values="win_rate")
    if existing_versions:
        pivot_wr = pivot_wr.reindex(existing_versions)

    sns.heatmap(
        pivot_wr, annot=True, fmt=".1f", cmap="RdYlGn", cbar_kws={"label": "Win Rate %"}
    )
    plt.title("RL Model Performance Heatmap (Win Rate %)")
    plt.xlabel("Opponent (Heuristic)")
    plt.ylabel("RL Model Version")

    # 3. Turns Analysis (Efficiency)
    plt.subplot(2, 2, 2)
    avg_turns = df.groupby("version")["avg_turns"].mean()
    if existing_versions:
        avg_turns = avg_turns.reindex(existing_versions)

    colors = sns.color_palette("viridis", len(avg_turns))
    avg_turns.plot(kind="bar", color=colors)
    plt.title("Average Battle Duration (Lower = More Decisive)")
    plt.xlabel("RL Model Version")
    plt.ylabel("Avg Turns per Battle")

    # 4. Success against Baselines
    plt.subplot(2, 2, 3)
    baselines = ["rdm", "mp", "sh"]
    baseline_df = df[df["opponent"].isin(baselines)]
    sns.barplot(
        data=baseline_df,
        x="version",
        y="win_rate",
        hue="opponent",
        order=existing_versions,
    )
    plt.axhline(50, color="red", linestyle="--", alpha=0.5)
    plt.title("Performance against Standard Baselines")
    plt.ylabel("Win Rate %")

    # 5. Evolution: Win Rate across Experts
    plt.subplot(2, 2, 4)
    experts = ["v1", "v2", "v3", "v4", "v5", "v6"]
    expert_df = df[df["opponent"].isin(experts)]
    sns.lineplot(data=expert_df, x="opponent", y="win_rate", hue="version", marker="o")
    plt.title("Expert Gauntlet Trend")
    plt.xlabel("Heuristic Version")
    plt.ylabel("Win Rate %")

    plt.tight_layout()
    report_file = Path("src/p04_rl_models/s03_evaluation/results/rl_model_report.png")
    plt.savefig(report_file, dpi=300)
    print(f"✅ Analysis report saved as: {report_file}")

    # 6. Print Ranking
    print("\n🏆 RL MODEL RANKING (Avg. Win Rate against all):")
    ranking = df.groupby("version")["win_rate"].mean().sort_values(ascending=False)
    for i, (ver, val) in enumerate(ranking.items(), 1):
        print(f"{i}. {ver}: {val:.2f}% Win Rate")


if __name__ == "__main__":
    generate_visual_report()
