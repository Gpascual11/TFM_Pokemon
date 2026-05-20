#!/usr/bin/env python
"""Heuristic Reliability Analyzer.

This script parses benchmark CSVs to analyze how often our heuristics
default to random moves due to indecision (fallbacks) or logic crashes (errors).
It prints a summarized table to the console and generates a bar chart.
"""

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from tabulate import tabulate


def analyze_directory(data_dir: Path) -> None:
    """Read CSVs in the target directory and aggregate fallback/error metrics."""
    all_data = []

    if not data_dir.exists():
        print(f"❌ Directory {data_dir} does not exist.")
        return

    csv_files = list(data_dir.glob("*.csv"))
    if not csv_files:
        print(f"⚠️ No CSV files found in {data_dir}.")
        return

    for file in csv_files:
        try:
            df = pd.read_csv(file)
        except Exception as e:
            print(f"Could not read {file}: {e}")
            continue

        # Ensure the new tracking columns exist in this CSV
        required_cols = ["heuristic", "turns", "decisions_us", "fallback_moves_us", "error_moves_us"]
        if not all(col in df.columns for col in required_cols):
            print(f"⏩ Skipping {file.name} - missing required metric columns (might be an older run).")
            continue

        # Aggregate the stats per heuristic agent found in the file
        for agent, group in df.groupby("heuristic"):
            all_data.append(
                {
                    "Agent": agent,
                    "Total Games": len(group),
                    "Total Turns": group["turns"].sum(),
                    "Total Decisions": group["decisions_us"].sum(),
                    "Fallback Moves": group["fallback_moves_us"].sum(),
                    "Error Moves": group["error_moves_us"].sum(),
                }
            )

    if not all_data:
        print("⚠️ No valid tracking data found to analyze.")
        return

    # Combine all data and group by Agent (in case of multiple files for the same agent)
    summary_df = pd.DataFrame(all_data)
    grouped = summary_df.groupby("Agent").sum().reset_index()

    # Calculate Rates
    grouped["Fallback Rate (%)"] = (grouped["Fallback Moves"] / grouped["Total Decisions"] * 100).fillna(0).round(2)
    grouped["Error Rate (%)"] = (grouped["Error Moves"] / grouped["Total Decisions"] * 100).fillna(0).round(2)

    # 1. Print Table
    print(f"\n📊 HEURISTIC RELIABILITY SUMMARY ({data_dir.name})")
    print(tabulate(grouped, headers="keys", tablefmt="github", showindex=False))

    # 2. Generate Graphic
    plot_path = data_dir / "fallback_analysis.png"
    fig, ax1 = plt.subplots(figsize=(10, 6))
    agents = grouped["Agent"]
    x = range(len(agents))

    ax1.bar(x, grouped["Fallback Rate (%)"], width=0.4, label="Fallback Rate (%)", align="center", color="#FFA500")
    ax1.bar(
        [i + 0.4 for i in x],
        grouped["Error Rate (%)"],
        width=0.4,
        label="Error Rate (%)",
        align="center",
        color="#E74C3C",
    )

    ax1.set_xlabel("Heuristic Agent", fontweight="bold")
    ax1.set_ylabel("Percentage of Total Decisions", fontweight="bold")
    ax1.set_title("Fallback and Error Rates per Heuristic", fontsize=14, fontweight="bold")
    ax1.set_xticks([i + 0.2 for i in x])
    ax1.set_xticklabels(agents)
    ax1.legend()

    # Add gridlines for easier reading
    ax1.grid(axis="y", linestyle="--", alpha=0.7)

    plt.tight_layout()
    plt.savefig(plot_path, dpi=300)
    print(f"\n📈 Graphic successfully saved to {plot_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze fallback and error rates from benchmark CSVs.")
    parser.add_argument(
        "--data-dir",
        type=str,
        default="data/1_vs_1/benchmarks/my_test_run",
        help="Directory containing the CSV files to analyze.",
    )
    args = parser.parse_args()
    analyze_directory(Path(args.data_dir))
