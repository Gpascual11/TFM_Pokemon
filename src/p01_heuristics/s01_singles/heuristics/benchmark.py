#!/usr/bin/env python
"""Benchmark Matrix V2 for Singles Heuristics.

Executes a round-robin tournament between all registered Singles heuristics
and baseline opponents. Designed for high-reliability long-running runs:

- **Memory Regulation**: Restarts servers every matchup and uses explicit GC.
- **Resilience**: Supports full checkpointing and physical CSV scanning to resume.
- **Scalability**: Distributes battles across multiple local ports in parallel.

Usage::

    # 1 000 games per matchup, 4 parallel ports, resumable
    uv run python src/p01_heuristics/s01_singles/heuristics/benchmark.py 1000 -p 4 --resume
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

# ---------------------------------------------------------------------------
# Package bootstrap
# ---------------------------------------------------------------------------
# This file lives at  src/p01_heuristics/s01_singles/heuristics/benchmark.py
# We need to walk 3 levels up (heuristics → s01_singles → p01_heuristics → src).
_DIR = Path(__file__).parent.resolve()
_SRC = _DIR.parent.parent.parent
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

__package__ = "p01_heuristics.s01_singles.heuristics"

from ..core.battle_manager import BattleManager  # noqa: E402
from ..core.factory import HeuristicFactory  # noqa: E402
from ..core.process_launcher import ProcessLauncher  # noqa: E402


# ---------------------------------------------------------------------------
# Matchup runner
# ---------------------------------------------------------------------------
def run_matchup(v_a: str, v_b: str, games: int, ports: list[int], data_dir: Path) -> dict:
    """Run a single matchup and return detailed metrics.

    Parameters
    ----------
    v_a : str
        Heuristic version under test (e.g. ``"v5"``).
    v_b : str
        Opponent version or baseline label.
    games : int
        Total number of battles to simulate.
    ports : list[int]
        Server port(s) to use.
    data_dir : Path
        Directory where the per-matchup CSV is written.

    Returns
    -------
    dict
        Keys: ``win_rate``, ``avg_turns``, ``avg_fainted_opp``,
        ``avg_hp_remaining``, ``total_games``.
    """
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
            batch_size=250,
        )
        csv_path = launcher.launch()
        del launcher
        gc.collect()

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
    return metrics


# ---------------------------------------------------------------------------
# Server management
# ---------------------------------------------------------------------------
def restart_servers(n_ports: int) -> None:
    """Kill existing Showdown servers and launch *n_ports* fresh instances.

    Waits 10 seconds after launch for Node.js workers to initialise.
    """
    print("\n♻️  RESTARTING SHOWDOWN SERVERS (Clearing Node.js RAM)...")
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


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> None:
    """Parse CLI arguments and run the full benchmark matrix."""
    parser = argparse.ArgumentParser(
        description="Round-robin benchmark matrix for all internal heuristic versions.",
    )
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
        help="Directory for per-matchup battle CSVs.",
    )
    parser.add_argument(
        "--output-csv",
        type=str,
        default="src/p01_heuristics/s01_singles/heuristics/results/benchmark_summary.csv",
        help="Path for the aggregated results CSV.",
    )
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    if data_dir.suffix == ".csv":
        data_dir = data_dir.parent
    data_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_file = data_dir / "checkpoint_v2.json"

    if len(args.ports) == 1 and args.ports[0] < 100:
        n_ports = args.ports[0]
        args.ports = [8000 + i for i in range(n_ports)]
    ports_list = args.ports

    logging.basicConfig(level=logging.WARNING)
    logging.getLogger("p01_heuristics").setLevel(logging.INFO)
    logging.getLogger("poke_env").setLevel(logging.ERROR)

    heuristics = sorted(HeuristicFactory.available_versions())
    baselines = ["random", "max_power", "simple_heuristic"]
    rows_v = heuristics
    cols_v = heuristics + baselines

    checkpoint_data: dict = {}
    if args.resume and checkpoint_file.exists():
        print(f"🔄 Resuming from checkpoint: {checkpoint_file}")
        with open(checkpoint_file) as f:
            checkpoint_data = json.load(f)

    print("🚀 Starting Benchmark Matrix V2")
    print(f"🔹 Data Directory: {data_dir}")
    print(f"📈 Total Matchups: {len(rows_v) * len(cols_v)}")
    print(f"📡 Serving on {len(ports_list)} port(s): {ports_list}")

    matchup_count = 0
    for v_a in rows_v:
        for v_b in cols_v:
            match_key = f"{v_a}_vs_{v_b}"

            if args.resume:
                if match_key in checkpoint_data:
                    print(f"⏩ Skipping {v_a} vs {v_b} (found in checkpoint)")
                    continue
                csv_path = data_dir / f"1_vs_1_{v_a}_vs_{v_b}.csv"
                if csv_path.exists():
                    try:
                        df_check = pd.read_csv(csv_path)
                        if len(df_check) >= args.total_games:
                            checkpoint_data[match_key] = {
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
                            print(f"⏩ Skipping {v_a} vs {v_b} (CSV already complete)")
                            continue
                    except Exception:
                        pass

            restart_servers(len(ports_list))

            metrics = run_matchup(v_a, v_b, args.total_games, ports_list, data_dir)
            checkpoint_data[match_key] = metrics
            matchup_count += 1

            with open(checkpoint_file, "w") as f:
                json.dump(checkpoint_data, f, indent=4)

            gc.collect()
            time.sleep(2)

    # --- Build summary CSV ---
    results_list = []
    for match_key, m in checkpoint_data.items():
        v_a, v_b = match_key.split("_vs_")
        results_list.append(
            {
                "version": v_a,
                "opponent": v_b,
                "win_rate": round(m["win_rate"], 2),
                "avg_turns": round(m["avg_turns"], 2),
                "avg_fainted_opp": round(m["avg_fainted_opp"], 2),
                "avg_hp_remaining": round(m["avg_hp_remaining"], 4),
                "total_games": m["total_games"],
            }
        )

    final_df = pd.DataFrame(results_list)
    Path(args.output_csv).parent.mkdir(parents=True, exist_ok=True)
    final_df.to_csv(args.output_csv, index=False)
    print(f"\n✅ MASTER SUMMARY SAVED TO: {args.output_csv}")

    # --- Terminal win-rate matrix ---
    table_rows = []
    for v_a in rows_v:
        row = [v_a]
        for v_b in cols_v:
            m = checkpoint_data.get(f"{v_a}_vs_{v_b}", {})
            row.append(f"{m.get('win_rate', 0.0):.1f}%")
        table_rows.append(row)

    headers = ["Heuristic \\ Opponent"] + cols_v
    print("\n" + "=" * 80)
    print("🏆 WIN RATE MATRIX (%)")
    print("=" * 80)
    print(tabulate(table_rows, headers=headers, tablefmt="grid"))
    print("=" * 80)


if __name__ == "__main__":
    main()
