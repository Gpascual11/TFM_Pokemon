"""Unified Heatmap Generator.
Reads experimental data and produces comparative visualizations.
"""

import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from pathlib import Path
import numpy as np

# Configuration
DEFAULT_DATA_DIR = Path("data/1_vs_1/benchmarks/unified")
DEFAULT_OUTPUT = Path("src/p01_heuristics/s01_singles/evaluation/results/full_heatmap.png")

def get_display_name(name):
    # Category prefixing
    internal = ["v1", "v2", "v3", "v4", "v5", "v6"]
    baselines = ["random", "max_power", "simple_heuristic", "abyssal", "one_step", "safe_one_step"]
    llm = ["pokechamp", "pokellmon"]
    
    if name in internal: return f"(H) {name}"
    if name in baselines: return f"(PE) {name}"
    if name in llm: return f"(LLM) {name}"
    return name

def generate_heatmap(data_dir: Path, output_path: Path):
    """Analyzes benchmark results and generates a comparative win-rate heatmap.
    
    Scans the provided directory for CSV files containing battle outcomes, 
    standardizes agent/opponent labels, calculates mean win rates for all 
    cross-matchups, and produces a high-fidelity Seaborn visualization.
    """
    all_files = list(data_dir.glob("*.csv"))
    if not all_files:
        print(f"⚠️ No data found in {data_dir}")
        return

    frames = []
    for f in all_files:
        try:
            df = pd.read_csv(f)
            # Standardize column names
            df = df.rename(columns={"pokechamp_agent": "agent", "heuristic": "agent", "opponent_type": "opponent"})
            frames.append(df[["agent", "opponent", "won"]])
        except Exception as e:
            print(f"Error reading {f.name}: {e}")

    if not frames: return
    df = pd.concat(frames, ignore_index=True)
    
    # Group by agent/opponent
    stats = df.groupby(["agent", "opponent"])["won"].mean().reset_index()
    
    # Pivot
    agents = sorted(df["agent"].unique())
    opponents = sorted(df["opponent"].unique())
    
    matrix = pd.DataFrame(index=agents, columns=opponents)
    for a in agents:
        for o in opponents:
            match = stats[(stats["agent"] == a) & (stats["opponent"] == o)]
            if not match.empty:
                matrix.loc[a, o] = match["won"].iloc[0] * 100
            elif a == o:
                matrix.loc[a, o] = 50.0
            else:
                # Try inverse
                rev = stats[(stats["agent"] == o) & (stats["opponent"] == a)]
                if not rev.empty:
                    matrix.loc[a, o] = (1 - rev["won"].iloc[0]) * 100

    matrix = matrix.apply(pd.to_numeric)
    
    # Prettify names
    matrix.index = [get_display_name(n) for n in matrix.index]
    matrix.columns = [get_display_name(n) for n in matrix.columns]

    # Plot
    plt.figure(figsize=(14, 10))
    sns.heatmap(matrix, annot=True, fmt=".1f", cmap="RdYlGn", cbar_kws={'label': 'Win Rate %'})
    plt.title("Unified Single Battles Benchmark", fontsize=16)
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    print(f"✅ Success! Heatmap saved to {output_path}")

if __name__ == "__main__":
    generate_heatmap(DEFAULT_DATA_DIR, DEFAULT_OUTPUT)
