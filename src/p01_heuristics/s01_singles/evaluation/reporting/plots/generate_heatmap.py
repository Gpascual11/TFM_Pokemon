"""Flexible Heatmap Generator (Scientific Style).

Can be pointed at any directory containing battle result CSVs to produce 
a high-fidelity win-rate heatmap for publications.
"""

import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Package bootstrap
# ---------------------------------------------------------------------------
_DIR = Path(__file__).parent.resolve()
_REPORTING = _DIR.parent
_EVAL = _REPORTING.parent
_SINGLES = _EVAL.parent
_SRC = _SINGLES.parent.parent
_ROOT = _SRC.parent

if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import argparse
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from p01_heuristics.s01_singles.evaluation.reporting.plots.styling import apply_premium_style, finalize_plot, get_display_name, RD_YL_GN_PREMIUM

def generate_heatmap(
    data_dir: Path, 
    output_path: Path, 
    title: str = "Win-Rate Correlation Matrix",
    filter_agents: list[str] | None = None,
    filter_opponents: list[str] | None = None
):
    """Analyzes results and generates a comparative win-rate heatmap."""
    apply_premium_style()
    
    all_files = list(data_dir.glob("*.csv"))
    if not all_files:
        print(f"⚠️ No data found in {data_dir}")
        return

    frames = []
    for f in all_files:
        try:
            df = pd.read_csv(f)
            # Standardize common column naming variations
            df = df.rename(columns={
                "pokechamp_agent": "agent", 
                "heuristic": "agent", 
                "opponent_type": "opponent",
                "opponent": "opponent"
            })
            if "agent" not in df.columns or "opponent" not in df.columns or "won" not in df.columns:
                continue
            frames.append(df[["agent", "opponent", "won"]])
        except Exception as e:
            print(f"Error reading {f.name}: {e}")

    if not frames: 
        print("⚠️ No valid data frames to process.")
        return
        
    df = pd.concat(frames, ignore_index=True)
    stats = df.groupby(["agent", "opponent"])["won"].mean().reset_index()
    
    # Priority order for axes
    ORDER = ["v1", "v2", "v3", "v4", "v5", "v6", "v7", "random", "max_power", "simple_heuristic", "abyssal", "one_step", "safe_one_step"]
    
    agents = sorted(df["agent"].unique(), key=lambda x: ORDER.index(x) if x in ORDER else 999)
    opponents = sorted(df["opponent"].unique(), key=lambda x: ORDER.index(x) if x in ORDER else 999)

    # Apply filters if provided
    if filter_agents:
        agents = [a for a in agents if a in filter_agents]
    if filter_opponents:
        opponents = [o for o in opponents if o in filter_opponents]

    if not agents or not opponents:
        print("⚠️  Filtering resulted in an empty matrix.")
        return
    
    matrix = pd.DataFrame(index=agents, columns=opponents)
    for a in agents:
        for o in opponents:
            match = stats[(stats["agent"] == a) & (stats["opponent"] == o)]
            if not match.empty:
                matrix.loc[a, o] = match["won"].iloc[0] * 100
            elif a == o:
                # Prioritize real data if it somehow exists, otherwise 50%
                matrix.loc[a, o] = 50.0 if match.empty else match["won"].iloc[0] * 100
            else:
                rev = stats[(stats["agent"] == o) & (stats["opponent"] == a)]
                if not rev.empty:
                    matrix.loc[a, o] = (1 - rev["won"].iloc[0]) * 100

    matrix = matrix.apply(pd.to_numeric)
    matrix.index = [get_display_name(n) for n in matrix.index]
    matrix.columns = [get_display_name(n) for n in matrix.columns]

    fig, ax = plt.subplots(figsize=(12, 10))
    sns.heatmap(
        matrix, annot=True, fmt=".1f", cmap=RD_YL_GN_PREMIUM, 
        vmin=0, vmax=100, linewidths=0.5, linecolor='#eee', square=False, ax=ax,
        cbar_kws={'label': 'Success Rate %', 'shrink': 0.7},
        annot_kws={"size": 10}
    )
    
    plt.xticks(rotation=45, ha='right')
    finalize_plot(fig, title=title, subtitle=f"Extracted from source dataset: {data_dir.name}")
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path)
    plt.close()
    print(f"✅ Success! Scientific heatmap saved to {output_path}")

def main():
    parser = argparse.ArgumentParser(description="Generate a win-rate heatmap from CSV results.")
    parser.add_argument("--data-dir", type=str, required=True, help="Path to CSV files")
    parser.add_argument("--output", type=str, default=None, help="Output PNG path. Defaults to heatmap.png in --data-dir.")
    parser.add_argument("--title", type=str, default="Matchup Win Rates", help="Plot title")
    parser.add_argument("--agents", nargs="+", help="Only include these agents in the heatmap")
    parser.add_argument("--opponents", nargs="+", help="Only include these opponents in the heatmap")
    args = parser.parse_args()
    
    data_dir = Path(args.data_dir)
    output_path = Path(args.output) if args.output else data_dir / "heatmap.png"

    generate_heatmap(
        data_dir, 
        output_path, 
        args.title,
        filter_agents=args.agents,
        filter_opponents=args.opponents
    )

if __name__ == "__main__":
    main()
