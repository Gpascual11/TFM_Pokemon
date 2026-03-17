#!/usr/bin/env python
"""CLI entry point for 2-vs-2 heuristic simulations.

Examples
--------
uv run python src/p01_heuristics/s02_doubles/run.py v6 random 100
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

# ---------------------------------------------------------------------------
# Package bootstrap
# ---------------------------------------------------------------------------
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_PARENT_DIR = os.path.dirname(_THIS_DIR)

if __package__ is None or __package__ == "":
    # Add the 'src' directory to sys.path
    _SRC_DIR = os.path.dirname(_PARENT_DIR)
    if _SRC_DIR not in sys.path:
        sys.path.insert(0, _SRC_DIR)

    # Set the package context correctly
    # Structure is src/p01_heuristics/s02_doubles
    __package__ = "p01_heuristics.s02_doubles"
    import importlib

    importlib.import_module(__package__)

from .core.battle_manager import BattleManager, OPPONENT_CHOICES  # noqa: E402
from .core.factory import HeuristicFactory  # noqa: E402
from .core.process_launcher import ProcessLauncher  # noqa: E402

_OPPONENT_LABELS = {
    "random": "RandomPlayer",
    "self": "Self-Play",
    "max_power": "MaxBasePowerPlayer",
    "simple_heuristic": "SimpleHeuristicsDoublesPlayer",
}


def _build_parser() -> argparse.ArgumentParser:
    versions = HeuristicFactory.available_versions()

    parser = argparse.ArgumentParser(
        description="Run batched Pokémon Showdown 2-vs-2 heuristic simulations.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Positional Arguments (Speed)
    parser.add_argument(
        "version",
        choices=versions,
        help=f"Heuristic version to test ({', '.join(versions)}).",
    )
    parser.add_argument(
        "opponent",
        nargs="?",
        default="random",
        help="Opponent version (v1-v6) or type (random, self, max_power, simple_heuristic).",
    )
    parser.add_argument(
        "total_games",
        type=int,
        nargs="?",
        default=1000,
        help="Total battles to simulate (default: 1000).",
    )

    # Optional Flags
    parser.add_argument(
        "-b",
        "--batch-size",
        type=int,
        default=500,
        help="Battles per batch call (default: 500).",
    )
    parser.add_argument(
        "-c",
        "--concurrent-battles",
        type=int,
        default=16,
        help="Max concurrent battles per process (default: 16).",
    )
    parser.add_argument("-p", "--ports", type=int, default=1, help="Number of ports to use (8000+)")
    parser.add_argument("--start-port", type=int, default=8000, help="Initial port number")
    parser.add_argument(
        "--data-dir",
        type=str,
        default="data/2_vs_2/runs",
        help="Output directory (default: data/2_vs_2/runs).",
    )
    parser.add_argument(
        "--battle-format",
        type=str,
        default="gen9randomdoublesbattle",
        help="Showdown battle format (default: gen9randomdoublesbattle).",
    )
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
    print(f"╔══════════════════════════════════════════════╗")
    print(f"║  Heuristic 2v2 Simulation — {args.version:>2s}               ║")
    print(f"╠══════════════════════════════════════════════╣")
    print(f"║  Total Games:        {args.total_games:>10,}              ║")
    print(f"║  Batch Size:         {args.batch_size:>10,}              ║")
    print(f"║  Concurrent Battles: {args.concurrent_battles:>10,}              ║")
    print(f"║  Server Ports:       {str(args.ports):<24s}║")
    print(f"║  Opponent:           {opp_label:<24s}║")
    print(f"║  Output Dir:         {args.data_dir:<24s}║")
    print(f"╚══════════════════════════════════════════════╝")


def main(argv: list[str] | None = None) -> None:
    """Parse CLI arguments and run the simulation."""
    args = _build_parser().parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    # Silence poke-env internal protocol logging
    logging.getLogger("poke_env").setLevel(logging.WARNING)

    _print_banner(args)
    ports = [args.start_port + i for i in range(args.ports)]

    if len(ports) == 1:
        mgr = BattleManager(
            version=args.version,
            server_url=f"ws://127.0.0.1:{ports[0]}/showdown/websocket",
            total_games=args.total_games,
            batch_size=args.batch_size,
            concurrent_battles=args.concurrent_battles,
            data_dir=args.data_dir,
            opponent=args.opponent,
            battle_format=args.battle_format,
        )
        csv_path = mgr.run()
    else:
        launcher = ProcessLauncher(
            version=args.version,
            ports=ports,
            total_games=args.total_games,
            batch_size=args.batch_size,
            concurrent_battles=args.concurrent_battles,
            data_dir=args.data_dir,
            opponent=args.opponent,
            battle_format=args.battle_format,
        )
        csv_path = launcher.launch()

    print(f"\n✅ Done! Results saved to: {csv_path}")


if __name__ == "__main__":
    main()
