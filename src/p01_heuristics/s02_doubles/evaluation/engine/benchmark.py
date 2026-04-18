import sys
from pathlib import Path

# Dynamic path resolution to find core modules
_this_dir = Path(__file__).parent.resolve()
_engine_dir = _this_dir
_eval_dir = _engine_dir.parent
_doubles_dir = _eval_dir.parent
_heuristics_dir = _doubles_dir.parent
_src_dir = _heuristics_dir.parent
_root_dir = _src_dir.parent
if str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))

import argparse
import gc
import subprocess
import time

import pandas as pd
from tabulate import tabulate

from p01_heuristics.s02_doubles.core.factory import HeuristicFactory
from p01_heuristics.s02_doubles.core.process_launcher import ProcessLauncher

DEFAULT_DATA_DIR = "data/2_vs_2/benchmarks/unified"


def get_csv_games(csv_path: Path) -> int:
    """Helper to count games in an existing CSV."""
    if not csv_path.exists():
        return 0
    try:
        df = pd.read_csv(csv_path)
        return len(df)
    except:
        return 0


def run_matchup(
    v_a: str, v_b: str, games: int, ports: list[int], data_dir: Path, battle_format: str
) -> tuple[dict, int]:
    """Run a specific matchup and return its summary metrics and games actually launched."""
    # Check if we need more games
    csv_path = data_dir / f"{v_a}_vs_{v_b}.csv"
    existing = get_csv_games(csv_path)

    games_ran = 0
    if existing >= games:
        print(f"      [doubles] {v_a} vs {v_b}: Found {existing} games. No new battles needed.")
    else:
        to_run = games - existing
        print(f"      [doubles] {v_a} vs {v_b}: Starting {to_run} more games (Total: {games})...")

        launcher = ProcessLauncher(
            version=v_a,
            opponent=v_b,
            total_games=to_run,
            ports=ports,
            data_dir=str(data_dir),
            batch_size=250,
            battle_format=battle_format,
        )
        launcher.launch()
        games_ran = to_run

    # Final tally
    df = pd.read_csv(csv_path)
    metrics = {
        "win_rate": (df["won"].sum() / len(df)) * 100,
        "avg_turns": df["turns"].mean(),
        "avg_fainted_opp": df["fainted_opp"].mean() if "fainted_opp" in df.columns else 0.0,
        "avg_hp_remaining": df["total_hp_us"].mean() if "total_hp_us" in df.columns else 0.0,
        "total_games": int(len(df)),
    }
    del df
    gc.collect()
    return metrics, games_ran


def restart_servers(n_ports: int):
    """Kills existing servers and starts fresh ones."""
    print("\n♻️  RESTARTING SHOWDOWN SERVERS (Clearing Node.js RAM)...")
    try:
        subprocess.run(["pkill", "-f", "pokemon-showdown"], check=False)
        time.sleep(2)
        subprocess.Popen(
            ["bash", "src/p05_scripts/p05_launch_custom_servers.sh", str(n_ports)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=str(_root_dir),
        )
        print("⏳ Waiting 20 seconds for servers to initialize...")
        time.sleep(20)
    except Exception as e:
        print(f"❌ Failed to restart servers: {e}")


def main():
    parser = argparse.ArgumentParser(description="Extended Doubles Benchmark Matrix V2.")
    parser.add_argument("total_games", type=int, help="Total games per matchup.")
    parser.add_argument("--ports", type=int, default=4, help="Number of ports to use (8000+)")
    parser.add_argument("--start-port", type=int, default=8000, help="Initial port number")
    parser.add_argument(
        "--battle-format",
        type=str,
        default="gen9randomdoublesbattle",
        help="Showdown battle format (e.g. gen9randomdoublesbattle).",
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default="data/2_vs_2/benchmarks/gens_10k_teams",
        help="Data directory for per-matchup CSVs.",
    )
    parser.add_argument(
        "--output-csv",
        type=str,
        default="src/p01_heuristics/s02_doubles/evaluation/results/benchmark_summary.csv",
        help="Final summary CSV.",
    )
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    # If using the default top-level directory, sub-folder by battle format
    if args.data_dir == "data/2_vs_2/benchmarks/gens_10k_teams":
        data_dir = data_dir / args.battle_format

    data_dir.mkdir(parents=True, exist_ok=True)

    # Define Participants
    versions = HeuristicFactory.available_versions()
    rows_v = versions
    cols_v = versions + ["random", "max_power", "simple_heuristic"]

    print(f"🚀 Starting Doubles Benchmark: {len(rows_v) * len(cols_v)} matchups total.")
    print(f"🔹 Output directory: {data_dir}")

    ports = [args.start_port + i for i in range(args.ports)]
    restart_servers(len(ports))

    matchup_count = 0
    active_since_restart = 0
    results_list = []

    for v_a in rows_v:
        for v_b in cols_v:
            # Print a clean header for the matchup
            print(f"\n⚔️  [{matchup_count + 1}/{len(rows_v) * len(cols_v)}] Executing {v_a} vs {v_b}...")

            # Only restart if we've actually run 5 active matchups since the last restart
            if active_since_restart >= 5:
                restart_servers(len(ports))
                active_since_restart = 0

            # Run Matchup
            metrics, games_ran = run_matchup(v_a, v_b, args.total_games, ports, data_dir, args.battle_format)
            results_list.append({"version": v_a, "opponent": v_b, **metrics})

            if games_ran > 0:
                active_since_restart += 1

            matchup_count += 1

    # Final Export
    if results_list:
        final_df = pd.DataFrame(results_list)
        final_df.to_csv(args.output_csv, index=False)
        print(f"\n✅ MASTER SUMMARY SAVED TO: {args.output_csv}")

        # Print Win Rate Matrix
        print("\n" + "=" * 80)
        print("🏆 DOUBLES WIN RATE MATRIX (%)")
        print("=" * 80)
        pivot_wr = final_df.pivot(index="version", columns="opponent", values="win_rate")
        print(tabulate(pivot_wr, headers="keys", tablefmt="psql", floatfmt=".1f"))
        print("=" * 80)


if __name__ == "__main__":
    main()
