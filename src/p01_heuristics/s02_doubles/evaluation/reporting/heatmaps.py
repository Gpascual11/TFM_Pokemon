"""Unified Heatmap Generator for Doubles.
Reads experimental data from unified or LLM benchmark directories and produces comparative visualizations.
"""

import argparse
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from pathlib import Path
import numpy as np
import sys

# ---------------------------------------------------------------------------
# Configuration & Constants
# ---------------------------------------------------------------------------
ROOT = Path(__file__).parent.parent.parent.parent.parent.parent.resolve()
DEFAULT_UNIFIED_DIR = ROOT / "data" / "benchmarks_doubles_unified"
DEFAULT_LLM_DIR = ROOT / "data" / "benchmarks_doubles_llm"
DEFAULT_OUT_DIR = Path(__file__).parent.parent / "results"

INTERNAL = ["v1", "v2", "v6"]
BASELINES = ["random", "max_power", "abyssal", "one_step", "vgc", "simple_heuristic"]
LLM = ["pokechamp", "pokellmon", "llm_vgc"]

def get_display_name(name: str) -> str:
    """Add prefixes to agent names for clearer categorization in the heatmap."""
    if name in INTERNAL:
        return f"(H) {name}"
    if name in BASELINES:
        return f"(B) {name}"
    if name in LLM:
        return f"(AI) {name}"
    return name

def generate_heatmap(data_dir: Path, output_path: Path, title: str):
    """Scan data_dir for CSVs and build a cross-matchup heatmap.
    
    Args:
        data_dir (Path): Source directory containing agent_vs_opponent.csv files.
        output_path (Path): Destination for the PNG file.
        title (str): Title of the chart.
    """
    all_files = list(data_dir.glob("*.csv"))
    # Filter out temp files
    all_files = [f for f in all_files if not f.name.startswith("_tmp_")]
    
    if not all_files:
        print(f"⚠️ No processed data found in {data_dir}. Skipping heatmap.")
        return

    frames = []
    for f in all_files:
        try:
            df = pd.read_csv(f)
            # Normalize column names: some versions might use 'heuristic', 'version', or 'agent'
            df = df.rename(columns={"version": "agent", "heuristic": "agent"})
            if "agent" not in df.columns or "opponent" not in df.columns or "won" not in df.columns:
                continue
            frames.append(df[["agent", "opponent", "won"]])
        except Exception as e:
            print(f"Error reading {f.name}: {e}")

    if not frames:
        print(f"⚠️ No valid data frames extracted from {data_dir}")
        return
        
    df = pd.concat(frames, ignore_index=True)
    stats = df.groupby(["agent", "opponent"])["won"].mean().reset_index()
    
    agents = sorted(df["agent"].unique())
    opponents = sorted(df["opponent"].unique())
    
    matrix = pd.DataFrame(index=agents, columns=opponents)
    for a in agents:
        for o in opponents:
            match = stats[(stats["agent"] == a) & (stats["opponent"] == o)]
            if not match.empty:
                matrix.loc[a, o] = match["won"].iloc[0] * 100
            elif a == o:
                matrix.loc[a, o] = 50.0  # Equal matchup for identical agents
            else:
                # Try to find the reciprocal matchup if current isn't directly available
                rev = stats[(stats["agent"] == o) & (stats["opponent"] == a)]
                if not rev.empty:
                    matrix.loc[a, o] = (1 - rev["won"].iloc[0]) * 100

    matrix = matrix.apply(pd.to_numeric)
    
    # Prettify labels
    matrix.index = [get_display_name(n) for n in matrix.index]
    matrix.columns = [get_display_name(n) for n in matrix.columns]

    # Plotting logic
    plt.figure(figsize=(14, 10))
    sns.heatmap(matrix, annot=True, fmt=".1f", cmap="RdYlGn", cbar_kws={'label': 'Win Rate %'})
    plt.title(title, fontsize=16)
    plt.xlabel("Opponent")
    plt.ylabel("Testing Agent")
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    print(f"✅ Success! Heatmap saved to {output_path}")

def main():
    parser = argparse.ArgumentParser(description="Doubles Heatmap Generator")
    parser.add_argument("--dir", type=str, help="Specifically point to a data directory")
    parser.add_argument("--out", type=str, help="Source of the output png")
    args = parser.parse_args()

    if args.dir:
        # Single custom run
        dir_path = Path(args.dir)
        out_path = Path(args.out) if args.out else DEFAULT_OUT_DIR / "custom_heatmap.png"
        generate_heatmap(dir_path, out_path, f"Doubles Benchmark: {dir_path.name}")
    else:
        # Standard runs: Unified and LLM
        generate_heatmap(
            DEFAULT_UNIFIED_DIR, 
            DEFAULT_OUT_DIR / "full_doubles_heatmap.png",
            "Unified Doubles Battles Benchmark (Heuristics vs Baselines)"
        )
        generate_heatmap(
            DEFAULT_LLM_DIR, 
            DEFAULT_OUT_DIR / "llm_doubles_heatmap.png",
            "LLM Doubles Battles Benchmark (AI vs Baselines)"
        )

if __name__ == "__main__":
    main()
