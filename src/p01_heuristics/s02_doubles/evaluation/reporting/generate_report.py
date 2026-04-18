import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import numpy as np


def generate_visual_report(
    csv_path="src/p01_heuristics/s02_doubles/evaluation/results/benchmark_summary.csv",
):
    """Generates a visual report for doubles heuristic performance."""
    try:
        df = pd.read_csv(csv_path)
    except FileNotFoundError:
        print(f"Error: {csv_path} not found. Run benchmark first.")
        return

    sns.set_theme(style="whitegrid")
    fig = plt.figure(figsize=(16, 12))

    # 1. Heatmap
    plt.subplot(2, 2, 1)
    pivot_wr = df.pivot(index="version", columns="opponent", values="win_rate")
    sns.heatmap(pivot_wr, annot=True, fmt=".1f", cmap="RdYlGn")
    plt.title("Doubles Heuristic Performance (Win Rate %)")

    # 2. Avg Turns
    plt.subplot(2, 2, 2)
    avg_turns = df.groupby("version")["avg_turns"].mean().sort_values()
    avg_turns.plot(kind="bar", color=sns.color_palette("magma", len(avg_turns)))
    plt.title("Average Doubles Battle Duration")
    plt.ylabel("Turns")

    # 3. Baselines
    plt.subplot(2, 2, 3)
    baselines = ["random", "max_power", "simple_heuristic"]
    baseline_df = df[df["opponent"].isin(baselines)]
    sns.barplot(data=baseline_df, x="version", y="win_rate", hue="opponent")
    plt.axhline(50, color="red", linestyle="--")
    plt.title("Doubles performance vs. Baselines")

    # 4. HP Correlation
    plt.subplot(2, 2, 4)
    sns.scatterplot(data=df, x="avg_turns", y="avg_hp_remaining", hue="version", s=100)
    plt.title("Turns vs. Survival in Doubles")

    plt.tight_layout()
    report_file = "src/p01_heuristics/s02_doubles/evaluation/results/benchmark_report.png"
    plt.savefig(report_file, dpi=300)
    print(f"✅ Doubles Analysis report saved as: {report_file}")

    print("\n🏆 DOUBLES RANKING:")
    ranking = df.groupby("version")["win_rate"].mean().sort_values(ascending=False)
    for i, (ver, val) in enumerate(ranking.items(), 1):
        print(f"{i}. {ver}: {val:.2f}% Win Rate")


if __name__ == "__main__":
    generate_visual_report()
