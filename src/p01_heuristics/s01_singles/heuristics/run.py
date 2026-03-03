#!/usr/bin/env python
"""CLI entry point for 1-vs-1 heuristic simulations.

Runs a single matchup (one heuristic version vs one opponent) for a
configurable number of battles and saves per-battle results to CSV.

Usage::

    # Quick 100-game run: v6 vs random on default port 8000
    uv run python src/p01_heuristics/s01_singles/heuristics/run.py v6 random 100

    # 1 000 games, 4 parallel ports
    uv run python src/p01_heuristics/s01_singles/heuristics/run.py v5 max_power 1000 -p 8000 8001 8002 8003
"""

from __future__ import annotations

import argparse
import importlib
import logging
import os
import sys

# ---------------------------------------------------------------------------
# Package bootstrap — ensures relative imports work when invoked directly.
# File lives at: src/p01_heuristics/s01_singles/heuristics/run.py
# ---------------------------------------------------------------------------
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_S01_DIR = os.path.dirname(_THIS_DIR)  # s01_singles/
_P01_DIR = os.path.dirname(_S01_DIR)  # p01_heuristics/
_SRC_DIR = os.path.dirname(_P01_DIR)  # src/

if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

__package__ = "p01_heuristics.s01_singles.heuristics"


importlib.import_module("p01_heuristics.s01_singles")

from ..core.battle_manager import BattleManager  # noqa: E402
from ..core.factory import HeuristicFactory  # noqa: E402
from ..core.process_launcher import ProcessLauncher  # noqa: E402

_OPPONENT_LABELS = {
    "random": "RandomPlayer",
    "self": "Self-Play",
    "max_power": "MaxBasePowerPlayer",
    "simple_heuristic": "SimpleHeuristicsPlayer",
}


def _build_parser() -> argparse.ArgumentParser:
    """Build and return the CLI argument parser."""
    versions = HeuristicFactory.available_versions()
    parser = argparse.ArgumentParser(
        description="Run batched Pokémon Showdown 1-vs-1 heuristic simulations.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "version",
        choices=versions,
        help=f"Heuristic version to test ({', '.join(versions)}).",
    )
    parser.add_argument(
        "opponent",
        nargs="?",
        default="random",
        help="Opponent: heuristic version (v1–v6) or baseline (random, max_power, simple_heuristic).",
    )
    parser.add_argument(
        "total_games",
        type=int,
        nargs="?",
        default=1000,
        help="Total battles to simulate (default: 1000).",
    )
    parser.add_argument("-b", "--batch-size", type=int, default=500, help="Battles per batch (default: 500).")
    parser.add_argument(
        "-c", "--concurrent-battles", type=int, default=16, help="Max concurrent battles (default: 16)."
    )
    parser.add_argument("-p", "--ports", type=int, nargs="+", default=[8000], help="Server port(s) (default: 8000).")
    parser.add_argument("--data-dir", type=str, default="data", help="Output directory (default: data).")
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity (default: INFO).",
    )
    return parser


def _print_banner(args: argparse.Namespace) -> None:
    """Print a formatted summary of simulation parameters."""
    opp_label = _OPPONENT_LABELS.get(args.opponent, args.opponent)
    print("╔══════════════════════════════════════════════╗")
    print(f"║  Heuristic 1v1 Simulation — {args.version:>2s}               ║")
    print("╠══════════════════════════════════════════════╣")
    print(f"║  Total Games:        {args.total_games:>10,}              ║")
    print(f"║  Batch Size:         {args.batch_size:>10,}              ║")
    print(f"║  Concurrent Battles: {args.concurrent_battles:>10,}              ║")
    print(f"║  Server Ports:       {str(args.ports):<24s}║")
    print(f"║  Opponent:           {opp_label:<24s}║")
    print(f"║  Output Dir:         {args.data_dir:<24s}║")
    print("╚══════════════════════════════════════════════╝")


def main(argv: list[str] | None = None) -> None:
    """Parse CLI arguments and run the simulation."""
    args = _build_parser().parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    logging.getLogger("poke_env").setLevel(logging.WARNING)

    _print_banner(args)

    if len(args.ports) == 1:
        mgr = BattleManager(
            version=args.version,
            server_url=f"ws://127.0.0.1:{args.ports[0]}/showdown/websocket",
            total_games=args.total_games,
            batch_size=args.batch_size,
            concurrent_battles=args.concurrent_battles,
            data_dir=args.data_dir,
            opponent=args.opponent,
        )
        csv_path = mgr.run()
    else:
        launcher = ProcessLauncher(
            version=args.version,
            ports=args.ports,
            total_games=args.total_games,
            batch_size=args.batch_size,
            concurrent_battles=args.concurrent_battles,
            data_dir=args.data_dir,
            opponent=args.opponent,
        )
        csv_path = launcher.launch()

    print(f"\n✅ Done! Results saved to: {csv_path}")


if __name__ == "__main__":
    main()
