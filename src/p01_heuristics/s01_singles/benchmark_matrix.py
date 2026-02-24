#!/usr/bin/env python
"""
Benchmark Matrix for Singles Heuristics.
Runs all registered heuristic versions against each other in a round-robin tournament.
"""

import argparse
import logging
import os
import sys
from tabulate import tabulate

# ---------------------------------------------------------------------------
# Package bootstrap
# ---------------------------------------------------------------------------
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_PARENT_DIR = os.path.dirname(_THIS_DIR)
_SRC_DIR = os.path.dirname(_PARENT_DIR)

if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

# Ensure package context
__package__ = "p01_heuristics.s01_singles"
import importlib

importlib.import_module(__package__)

from .core.factory import HeuristicFactory
from .core.battle_manager import BattleManager
from .core.process_launcher import ProcessLauncher


def run_matchup(v_a: str, v_b: str, games: int, ports: list[int]) -> float:
    """Run a single matchup and return the win rate of v_a."""
    print(f"\n⚔️  MATCHUP: {v_a} vs {v_b} ({games} games)...")

    # We use a temp directory or common data dir
    data_dir = "data/benchmarks"

    if len(ports) == 1:
        mgr = BattleManager(
            version=v_a,
            opponent=v_b,
            total_games=games,
            server_url=f"ws://127.0.0.1:{ports[0]}/showdown/websocket",
            data_dir=data_dir,
            batch_size=min(games, 500),
        )
        csv_path = mgr.run()
    else:
        launcher = ProcessLauncher(
            version=v_a,
            opponent=v_b,
            total_games=games,
            ports=ports,
            data_dir=data_dir,
            batch_size=min(games, 500),
        )
        csv_path = launcher.launch()

    # Extract winrate from the CSV generated
    import pandas as pd

    df = pd.read_csv(csv_path)
    winrate = (df["won"].sum() / len(df)) * 100
    return winrate


def main():
    parser = argparse.ArgumentParser(
        description="Run a round-robin benchmark matrix for all heuristics."
    )
    parser.add_argument(
        "total_games", type=int, help="Number of games per matchup pair."
    )
    parser.add_argument(
        "-p",
        "--ports",
        type=int,
        nargs="+",
        default=[8000],
        help="Server ports to use.",
    )
    args = parser.parse_args()

    # Silence verbose logs
    logging.basicConfig(level=logging.WARNING)
    logging.getLogger("p01_heuristics").setLevel(logging.INFO)
    logging.getLogger("poke_env").setLevel(logging.ERROR)

    # Heuristic versions
    heuristics = sorted(HeuristicFactory.available_versions())
    # Baselines requested by user
    baselines = ["random", "max_power", "simple_heuristic"]

    # We test every heuristic against every heuristic AND every baseline
    rows_v = heuristics
    cols_v = heuristics + baselines

    matrix = {v: {} for v in rows_v}

    print(f"🚀 Starting Benchmark Matrix")
    print(f"🔹 Heuristics: {heuristics}")
    print(f"🔹 Baselines: {baselines}")
    print(f"📈 Total Matchups: {len(rows_v) * len(cols_v)}")

    for v_a in rows_v:
        for v_b in cols_v:
            wr = run_matchup(v_a, v_b, args.total_games, args.ports)
            matrix[v_a][v_b] = wr

    # Prepare table for display
    headers = ["Heuristic \\ Opponent"] + cols_v
    rows = []
    for v_a in rows_v:
        row = [v_a]
        for v_b in cols_v:
            wr = matrix[v_a][v_b]
            row.append(f"{wr:.1f}%")
        rows.append(row)

    print("\n" + "=" * 80)
    print("🏆 HEURISTIC BATTLE MATRIX - WIN RATES (%)")
    print("=" * 80)
    print(tabulate(rows, headers=headers, tablefmt="grid"))
    print("=" * 80)
    print(f"Results saved in data/benchmarks/")


if __name__ == "__main__":
    main()
