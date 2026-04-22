import argparse
import pandas as pd
from pathlib import Path
from tabulate import tabulate

def generate_summary(data_dir: Path, output_csv: Path):
    """Reads all X_vs_Y.csv files in data_dir and generates a summary report."""
    csv_files = list(data_dir.glob("*.csv"))
    # Filter out the summary file itself if it exists
    csv_files = [f for f in csv_files if "vs" in f.name]
    
    if not csv_files:
        print(f"❌ No matchup CSVs found in {data_dir}")
        return

    results_list = []
    for f in csv_files:
        # Expected filename: agent_vs_opponent.csv
        try:
            name = f.stem
            parts = name.split("_vs_")
            if len(parts) != 2:
                continue
            
            v_a, v_b = parts
            df = pd.read_csv(f)
            
            metrics = {
                "version": v_a,
                "opponent": v_b,
                "win_rate": (df["won"].sum() / len(df)) * 100,
                "avg_turns": df["turns"].mean(),
                "avg_fainted_opp": df["fainted_opp"].mean() if "fainted_opp" in df.columns else 0.0,
                "avg_hp_remaining": df["total_hp_us"].mean() if "total_hp_us" in df.columns else 0.0,
                "total_games": int(len(df)),
            }
            results_list.append(metrics)
        except Exception as e:
            print(f"⚠️ Error processing {f.name}: {e}")

    if results_list:
        final_df = pd.DataFrame(results_list)
        final_df.to_csv(output_csv, index=False)
        print(f"✅ Master summary generated: {output_csv}")
        
        print("\n🏆 DOUBLES WIN RATE MATRIX (%)")
        pivot_wr = final_df.pivot(index="version", columns="opponent", values="win_rate")
        print(tabulate(pivot_wr, headers="keys", tablefmt="psql", floatfmt=".1f"))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=str, required=True, help="Path to raw CSV results.")
    parser.add_argument("--output", type=str, default=None, help="Output summary CSV.")
    args = parser.parse_args()
    
    data_path = Path(args.data_dir)
    output_path = Path(args.output) if args.output else data_path / "benchmark_summary.csv"
    
    generate_summary(data_path, output_path)
