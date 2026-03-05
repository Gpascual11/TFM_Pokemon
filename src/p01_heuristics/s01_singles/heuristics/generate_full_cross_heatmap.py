"""Generates a full cross-matchup heatmap for Heuristics, Poke-env Baselines, and Pokechamp Agents.
Excludes LLM agents (pokechamp, pokellmon).
Uses data from:
- data/benchmarks_singles_v3/
- data/benchmarks_pokechamp_parallel/
"""

import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from pathlib import Path
import numpy as np

# Configuration
DIR_V3 = Path("data/benchmarks_singles_v3")
DIR_PC = Path("data/benchmarks_pokechamp_parallel")
OUTPUT_DIR = Path("src/p01_heuristics/s01_singles/heuristics/results/v3")
OUTPUT_PNG = OUTPUT_DIR / "full_cross_heatmap.png"

# Agents to include
HEURISTICS = ["v1", "v2", "v3", "v4", "v5", "v6"]
BASELINES = ["random", "max_power", "simple_heuristic"]
POKECHAMP = ["abyssal", "one_step", "safe_one_step"]

ALL_AGENTS = HEURISTICS + BASELINES + POKECHAMP

def load_v3_data():
    """Load Heuristic vs Heuristic/Baseline data."""
    all_files = list(DIR_V3.glob("1_vs_1_*.csv"))
    frames = []
    for f in all_files:
        try:
            df = pd.read_csv(f)
            # Normalizing to: agent, opponent, won
            frames.append(df.rename(columns={"heuristic": "agent", "opponent_type": "opponent"})[["agent", "opponent", "won"]])
        except Exception as e:
            print(f"Error reading {f}: {e}")
    return frames

def load_pc_data():
    """Load Pokechamp vs Everyone data."""
    all_files = list(DIR_PC.glob("pokechamp_*_vs_*.csv"))
    frames = []
    for f in all_files:
        try:
            df = pd.read_csv(f)
            # skip LLMs
            agent = df["pokechamp_agent"].iloc[0]
            opponent = df["opponent"].iloc[0]
            if agent in ["pokechamp", "pokellmon"] or opponent in ["pokechamp", "pokellmon"]:
                continue
            
            # Normalizing to: agent, opponent, won
            frames.append(df.rename(columns={"pokechamp_agent": "agent"})[["agent", "opponent", "won"]])
        except Exception as e:
            print(f"Error reading {f}: {e}")
    return frames

def get_display_name(name):
    if name in HEURISTICS: return f"(H) {name}"
    if name in BASELINES: return f"(PE) {name}"
    if name in POKECHAMP: return f"(PC) {name}"
    return name

def main():
    frames = load_v3_data() + load_pc_data()
    if not frames:
        print("No data found!")
        return
    
    df = pd.concat(frames, ignore_index=True)
    
    # Calculate mean win rate
    stats = df.groupby(["agent", "opponent"])["won"].mean().reset_index()
    
    # Create the matrix
    # We want rows to be 'agents' and columns to be 'opponents'
    matrix = pd.DataFrame(index=ALL_AGENTS, columns=ALL_AGENTS)
    
    for agent in ALL_AGENTS:
        for opp in ALL_AGENTS:
            # Try to find WR(agent vs opp)
            match = stats[(stats["agent"] == agent) & (stats["opponent"] == opp)]
            if not match.empty:
                matrix.loc[agent, opp] = match["won"].iloc[0] * 100
            else:
                # Try to infer from WR(opp vs agent)
                reverse_match = stats[(stats["agent"] == opp) & (stats["opponent"] == agent)]
                if not reverse_match.empty:
                    matrix.loc[agent, opp] = (1 - reverse_match["won"].iloc[0]) * 100
                elif agent == opp:
                    matrix.loc[agent, opp] = 50.0  # Identity
                else:
                    matrix.loc[agent, opp] = np.nan

    # Convert to numeric
    matrix = matrix.apply(pd.to_numeric)
    
    # Prefix display names
    matrix.index = [get_display_name(n) for n in matrix.index]
    matrix.columns = [get_display_name(n) for n in matrix.columns]
    
    # Setup plotting
    sns.set_theme(style="whitegrid", font_scale=1.1)
    plt.figure(figsize=(16, 12))
    
    ax = sns.heatmap(
        matrix, 
        annot=True, 
        fmt=".1f", 
        cmap="RdYlGn", 
        cbar_kws={'label': 'Win Rate %'},
        linewidths=.5,
        vmin=0, vmax=100
    )
    
    plt.title("Full Heuristics & Agents Cross-Matchup Benchmark (No LLMs)", fontsize=18, pad=20)
    plt.xlabel("Opponent Agent", fontsize=14)
    plt.ylabel("Testing Agent", fontsize=14)
    
    # Add vertical/horizontal lines to separate categories
    h_idx = len(HEURISTICS)
    pe_idx = h_idx + len(BASELINES)
    
    for idx in [h_idx, pe_idx]:
        plt.axvline(x=idx, color='black', lw=2)
        plt.axhline(y=idx, color='black', lw=2)
    
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    plt.savefig(OUTPUT_PNG, dpi=300, bbox_inches="tight")
    print(f"✅ Success! Heatmap saved to {OUTPUT_PNG}")
    
    # Print summary
    print("\n📋 FULL WIN RATE MATRIX (%)")
    print(matrix.to_string())

if __name__ == "__main__":
    main()
