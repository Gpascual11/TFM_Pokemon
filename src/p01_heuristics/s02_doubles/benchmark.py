"""Benchmark Matrix V2 for 2-vs-2 Heuristics.

Calculates win rates, average turns, and detailed team metrics for all doubles matchups.
Includes automatic server management and checkpoint/resume support.
"""

import argparse
import asyncio
import json
import gc
import subprocess
import time
import pandas as pd
from pathlib import Path
from tabulate import tabulate

# Dynamic path resolution to find core modules
import os
import sys

_this_dir = Path(__file__).parent.resolve()
_src_dir = _this_dir.parent.parent  # src
if str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))

# Absolute imports from the package
from p01_heuristics.s02_doubles.core.factory import HeuristicFactory
from p01_heuristics.s02_doubles.core.battle_manager import BattleManager
from p01_heuristics.s02_doubles.core.process_launcher import ProcessLauncher


def run_matchup(
    v_a: str, v_b: str, games: int, ports: list[int], data_dir: Path
) -> dict:
    """Run a specific matchup and return its summary metrics."""
    print(f"\n⚔️  MATCHUP: {v_a} vs {v_b} ({games} games)...")

    # Run the simulation
    launcher = ProcessLauncher(
        version=v_a,
        opponent=v_b,
        total_games=games,
        ports=ports,
        data_dir=str(data_dir),
        batch_size=250,  # Safe batch size for memory
    )
    csv_path = launcher.launch()

    # Calculate metrics from the merged CSV
    df = pd.read_csv(csv_path)

    metrics = {
        "win_rate": (df["won"].sum() / len(df)) * 100,
        "avg_turns": df["turns"].mean(),
        "avg_fainted_opp": df["fainted_opp"].mean()
        if "fainted_opp" in df.columns
        else 0.0,
        "avg_hp_remaining": df["total_hp_us"].mean()
        if "total_hp_us" in df.columns
        else 0.0,
        "total_games": int(len(df)),
    }

    # Clean up large objects and trigger GC
    del df
    gc.collect()

    return metrics


def restart_servers(n_ports: int):
    """Kills existing servers and starts fresh ones."""
    print(f"\n♻️  RESTARTING SHOWDOWN SERVERS (Clearing Node.js RAM)...")
    try:
        subprocess.run(["pkill", "-f", "pokemon-showdown"], check=False)
        time.sleep(2)
        subprocess.Popen(
            ["bash", "src/p03_scripts/p03_launch_custom_servers.sh", str(n_ports)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        print("⏳ Waiting 10 seconds for servers to initialize...")
        time.sleep(10)
    except Exception as e:
        print(f"❌ Failed to restart servers: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Extended Doubles Benchmark Matrix V2."
    )
    parser.add_argument("total_games", type=int, help="Total games per matchup.")
    parser.add_argument(
        "--ports",
        type=int,
        nargs="+",
        default=[8000, 8001, 8002, 8003],
        help="Server ports.",
    )
    parser.add_argument("--resume", action="store_true", help="Resume from checkpoint.")
    parser.add_argument(
        "--data-dir",
        type=str,
        default="data/benchmarks_doubles_v3",
        help="Data directory.",
    )
    parser.add_argument(
        "--output-csv",
        type=str,
        default="src/p01_heuristics/s02_doubles/results/benchmark_summary.csv",
        help="Final summary CSV.",
    )
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_file = data_dir / "checkpoint_v2.json"

    # Define Participants
    versions = HeuristicFactory.available_versions()
    rows_v = versions
    cols_v = versions + ["random", "max_power", "simple_heuristic"]

    # Initialize or Load Checkpoint
    checkpoint_data = {}
    if args.resume and checkpoint_file.exists():
        print(f"🔄 Resuming from checkpoint: {checkpoint_file}")
        with open(checkpoint_file, "r") as f:
            checkpoint_data = json.load(f)

    print(f"🚀 Starting Doubles Benchmark Matrix V2")
    print(f"🔹 Folder: {data_dir}")
    print(f"📈 Total Matchups: {len(rows_v) * len(cols_v)}")

    restart_servers(len(args.ports))

    matchup_count = 0
    results_list = []

    for v_a in rows_v:
        for v_b in cols_v:
            match_key = f"{v_a}_vs_{v_b}"

            if matchup_count > 0 and matchup_count % 5 == 0:
                restart_servers(len(args.ports))

            # Skip logic
            if args.resume:
                if match_key in checkpoint_data:
                    print(f"⏩ Skipping {v_a} vs {v_b} (found in checkpoint)")
                    results_list.append(
                        {"version": v_a, "opponent": v_b, **checkpoint_data[match_key]}
                    )
                    matchup_count += 1
                    continue

                # Check for completed file regardless of JSON
                csv_path = data_dir / f"2_vs_2_{v_a}_vs_{v_b}.csv"
                if csv_path.exists():
                    try:
                        df_check = pd.read_csv(csv_path)
                        if len(df_check) >= args.total_games:
                            metrics = {
                                "win_rate": (df_check["won"].sum() / len(df_check))
                                * 100,
                                "avg_turns": df_check["turns"].mean(),
                                "avg_fainted_opp": df_check["fainted_opp"].mean()
                                if "fainted_opp" in df_check.columns
                                else 0.0,
                                "avg_hp_remaining": df_check["total_hp_us"].mean()
                                if "total_hp_us" in df_check.columns
                                else 0.0,
                                "total_games": int(len(df_check)),
                            }
                            print(
                                f"⏩ Skipping {v_a} vs {v_b} (Found complete CSV: {len(df_check)} games)"
                            )
                            checkpoint_data[match_key] = metrics
                            results_list.append(
                                {"version": v_a, "opponent": v_b, **metrics}
                            )
                            matchup_count += 1
                            continue
                    except:
                        pass

            # Run Matchup
            metrics = run_matchup(v_a, v_b, args.total_games, args.ports, data_dir)
            checkpoint_data[match_key] = metrics
            results_list.append({"version": v_a, "opponent": v_b, **metrics})
            matchup_count += 1

            # Save checkpoint
            with open(checkpoint_file, "w") as f:
                json.dump(checkpoint_data, f, indent=4)

    # Final Export
    if results_list:
        final_df = pd.DataFrame(results_list)
        final_df.to_csv(args.output_csv, index=False)
        print(f"\n✅ MASTER SUMMARY SAVED TO: {args.output_csv}")

        # Print Win Rate Matrix
        print("\n" + "=" * 80)
        print("🏆 DOUBLES WIN RATE MATRIX (%)")
        print("=" * 80)
        pivot_wr = final_df.pivot(
            index="version", columns="opponent", values="win_rate"
        )
        print(tabulate(pivot_wr, headers="keys", tablefmt="psql", floatfmt=".1f"))
        print("=" * 80)


if __name__ == "__main__":
    main()
