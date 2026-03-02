#!/usr/bin/env python
"""
Benchmark Matrix V2 for Singles Heuristics.

This script executes a round-robin tournament between all registered Singles heuristics
and baseline opponents. It is designed for high-reliability long-running runs:
- Memory Regulation: Restarts servers every matchup and uses explicit GC.
- Resilience: Supports full checkpointing and physical CSV scanning to resume.
- Scalability: Distributes battles across multiple local ports in parallel.
"""

import argparse
import gc
import json
import logging
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd
from tabulate import tabulate

# --- Package Bootstrap ---
# Ensures the script can be run directly while maintaining absolute package imports.
_DIR = Path(__file__).parent.resolve()
_SRC = _DIR.parent.parent
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

__package__ = "p01_heuristics.s01_singles"
from .core.battle_manager import BattleManager
from .core.factory import HeuristicFactory
from .core.process_launcher import ProcessLauncher


def run_matchup(v_a: str, v_b: str, games: int, ports: list[int], data_dir: Path) -> dict:
    """Run a single matchup and return detailed metrics."""
    print(f"\n⚔️  MATCHUP: {v_a} vs {v_b} ({games} games)...")

    if len(ports) == 1:
        mgr = BattleManager(
            version=v_a,
            opponent=v_b,
            total_games=games,
            server_url=f"ws://127.0.0.1:{ports[0]}/showdown/websocket",
            data_dir=str(data_dir),
            batch_size=min(games, 500),
        )
        csv_path = mgr.run()
        del mgr
        gc.collect()
    else:
        launcher = ProcessLauncher(
            version=v_a,
            opponent=v_b,
            total_games=games,
            ports=ports,
            data_dir=str(data_dir),
            batch_size=250,  # Batch size matched to server capacity
        )
        csv_path = launcher.launch()
        del launcher
        gc.collect()

    # Extract detailed metrics from the CSV
    df = pd.read_csv(csv_path)

    metrics = {
        "win_rate": (df["won"].sum() / len(df)) * 100,
        "avg_turns": df["turns"].mean(),
        "avg_fainted_opp": df["fainted_opp"].mean() if "fainted_opp" in df.columns else 0.0,
        "avg_hp_remaining": df["total_hp_us"].mean() if "total_hp_us" in df.columns else 0.0,
        "total_games": int(len(df)),
    }

    # Explicit cleanup to keep main process lean
    del df
    gc.collect()

    return metrics


def restart_servers(n_ports: int):
    """Kills existing servers and starts fresh ones."""
    print("\n♻️  RESTARTING SHOWDOWN SERVERS (Clearing Node.js RAM)...")
    try:
        # Kill any node processes running showdown
        subprocess.run(["pkill", "-f", "pokemon-showdown"], check=False)
        time.sleep(2)
        # Launch new ones
        subprocess.Popen(
            ["bash", "src/p03_scripts/p03_launch_custom_servers.sh", str(n_ports)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        # Wait for servers to boot
        print("⏳ Waiting 10 seconds for servers to initialize...")
        time.sleep(10)
    except Exception as e:
        print(f"❌ Failed to restart servers: {e}")


def main():
    parser = argparse.ArgumentParser(description="Extended Benchmark Matrix V2 with detailed metrics.")
    parser.add_argument("total_games", type=int, help="Number of games per matchup pair.")
    parser.add_argument(
        "-p",
        "--ports",
        type=int,
        nargs="+",
        default=[8000],
        help="Server ports (e.g. 8000 8001) or number of parallel ports (e.g. 4).",
    )
    parser.add_argument("--resume", action="store_true", help="Resume from previous checkpoint.")
    parser.add_argument(
        "--data-dir",
        type=str,
        default="data/benchmarks_v2",
        help="Folder for battle CSVs.",
    )
    parser.add_argument(
        "--output-csv",
        type=str,
        default="src/p01_heuristics/s01_singles/results/benchmark_summary.csv",
        help="Filename for the results summary.",
    )
    args = parser.parse_args()

    # Configuration
    data_dir = Path(args.data_dir)
    if data_dir.suffix == ".csv":
        data_dir = data_dir.parent
    data_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_file = data_dir / "checkpoint_v2.json"

    # Smart port expansion: Convert "-p 4" into [8000, 8001, 8002, 8003]
    if len(args.ports) == 1 and args.ports[0] < 100:
        n_ports = args.ports[0]
        args.ports = [8000 + i for i in range(n_ports)]

    # Final port list for the rest of the script
    ports_list = args.ports

    # Silence verbose logs
    logging.basicConfig(level=logging.WARNING)
    logging.getLogger("p01_heuristics").setLevel(logging.INFO)
    logging.getLogger("poke_env").setLevel(logging.ERROR)

    # Heuristics and Baselines
    heuristics = sorted(HeuristicFactory.available_versions())
    baselines = ["random", "max_power", "simple_heuristic"]
    rows_v = heuristics
    cols_v = heuristics + baselines

    # Initialize or Load Matrix
    full_data = {}  # Flat list of results for CSV
    checkpoint_data = {}  # Nested dict for resume logic

    if args.resume and checkpoint_file.exists():
        print(f"🔄 Resuming from checkpoint: {checkpoint_file}")
        with open(checkpoint_file) as f:
            checkpoint_data = json.load(f)

    print("🚀 Starting Benchmark Matrix V2")
    print(f"🔹 Data Directory: {data_dir}")
    print(f"📈 Total Matchups to evaluate: {len(rows_v) * len(cols_v)}")
    print(f"📡 Serving on {len(ports_list)} parallel ports: {ports_list}")

    matchup_count = 0
    for v_a in rows_v:
        for v_b in cols_v:
            match_key = f"{v_a}_vs_{v_b}"

            # Skip logic: Only if resume is active
            if args.resume:
                # Check checkpoint
                if match_key in checkpoint_data:
                    print(f"⏩ Skipping {v_a} vs {v_b} (found in checkpoint)")
                    continue

                # Check physical CSV
                csv_path = data_dir / f"1_vs_1_{v_a}_vs_{v_b}.csv"
                if csv_path.exists():
                    try:
                        df_check = pd.read_csv(csv_path)
                        if len(df_check) >= args.total_games:
                            metrics = {
                                "win_rate": (df_check["won"].sum() / len(df_check)) * 100,
                                "avg_turns": df_check["turns"].mean(),
                                "avg_fainted_opp": df_check["fainted_opp"].mean()
                                if "fainted_opp" in df_check.columns
                                else 0.0,
                                "avg_hp_remaining": df_check["total_hp_us"].mean()
                                if "total_hp_us" in df_check.columns
                                else 0.0,
                                "total_games": int(len(df_check)),
                            }
                            checkpoint_data[match_key] = metrics
                            print(f"⏩ Skipping {v_a} vs {v_b} (CSV already complete)")
                            continue
                    except Exception:
                        pass

            # Launch Matchup
            # Note: servers are restarted here (and NOT skipped) to clear Node.js memory
            restart_servers(len(ports_list))

            metrics = run_matchup(v_a, v_b, args.total_games, ports_list, data_dir)
            checkpoint_data[match_key] = metrics
            matchup_count += 1

            # Save checkpoint
            with open(checkpoint_file, "w") as f:
                json.dump(checkpoint_data, f, indent=4)

            # Explicit cleanup and sleep to prevent memory creep & socket exhaustion
            gc.collect()
            time.sleep(2)

    # Convert results to a flat list for pandas
    results_list = []
    for match_key, m in checkpoint_data.items():
        v_a, v_b = match_key.split("_vs_")
        res = {
            "version": v_a,
            "opponent": v_b,
            "win_rate": round(m["win_rate"], 2),
            "avg_turns": round(m["avg_turns"], 2),
            "avg_fainted_opp": round(m["avg_fainted_opp"], 2),
            "avg_hp_remaining": round(m["avg_hp_remaining"], 4),
            "total_games": m["total_games"],
        }
        results_list.append(res)

    # Save Master CSV
    final_df = pd.DataFrame(results_list)
    final_df.to_csv(args.output_csv, index=False)
    print(f"\n✅ MASTER SUMMARY SAVED TO: {args.output_csv}")

    # Display Win Rate Grid (Terminal remains useful)
    table_rows = []
    for v_a in rows_v:
        row = [v_a]
        for v_b in cols_v:
            m = checkpoint_data.get(f"{v_a}_vs_{v_b}", {})
            wr = m.get("win_rate", 0.0)
            row.append(f"{wr:.1f}%")
        table_rows.append(row)

    headers = ["Heuristic \\ Opponent"] + cols_v
    print("\n" + "=" * 80)
    print("🏆 WIN RATE MATRIX (%)")
    print("=" * 80)
    print(tabulate(table_rows, headers=headers, tablefmt="grid"))
    print("=" * 80)


if __name__ == "__main__":
    main()
