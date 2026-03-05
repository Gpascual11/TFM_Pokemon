"""Generates a cross-matchup heatmap for all heuristic versions (v1-v6) and baselines.
Uses data from data/benchmarks_singles_v3/
"""

import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from pathlib import Path
import numpy as np

# Configuration
DATA_DIR = Path("data/benchmarks_singles_v3")
OUTPUT_DIR = Path("src/p01_heuristics/s01_singles/heuristics/results/v3")
OUTPUT_PNG = OUTPUT_DIR / "heuristics_cross_heatmap.png"

# Define order for visual clarity
HEURISTICS = ["v1", "v2", "v3", "v4", "v5", "v6"]
BASELINES = ["random", "max_power", "simple_heuristic"]

AGENT_ORDER = HEURISTICS
OPPONENT_ORDER = HEURISTICS + BASELINES

def load_data():
    all_files = list(DATA_DIR.glob("1_vs_1_*.csv"))
    if not all_files:
        print(f"No files found in {DATA_DIR}")
        return None
    
    frames = []
    for f in all_files:
        try:
            df = pd.read_csv(f)
            # The columns are: battle_id, heuristic, opponent_type, winner, won, ...
            frames.append(df[["heuristic", "opponent_type", "won"]])
        except Exception as e:
            print(f"Error reading {f}: {e}")
            
    return pd.concat(frames, ignore_index=True)

def main():
    df = load_data()
    if df is None: return
    
    # Calculate mean win rate (in %)
    pivot = df.groupby(["heuristic", "opponent_type"])["won"].mean().unstack() * 100
    
    # Reindex to force our desired order
    pivot = pivot.reindex(index=AGENT_ORDER, columns=OPPONENT_ORDER)
    
    # Setup plotting
    sns.set_theme(style="whitegrid", font_scale=1.2)
    plt.figure(figsize=(14, 10))
    
    # Create heatmap
    ax = sns.heatmap(
        pivot, 
        annot=True, 
        fmt=".1f", 
        cmap="RdYlGn", 
        cbar_kws={'label': 'Win Rate %'},
        linewidths=.5,
        vmin=0, vmax=100
    )
    
    plt.title("Heuristics Cross-Matchup Benchmark (v1-v6 vs All)", fontsize=16, pad=20)
    plt.xlabel("Opponent", fontsize=14)
    plt.ylabel("Heuristic Agent", fontsize=14)
    
    # Add vertical line to separate Heuristics from Baselines in columns
    plt.axvline(x=len(HEURISTICS), color='black', lw=2)
    
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    plt.savefig(OUTPUT_PNG, dpi=300, bbox_inches="tight")
    print(f"✅ Success! Heatmap saved to {OUTPUT_PNG}")
    
    # Also print a summary table to terminal
    print("\n📋 WIN RATE SUMMARY TABLE (%)")
    print(pivot.to_string())

if __name__ == "__main__":
    main()
