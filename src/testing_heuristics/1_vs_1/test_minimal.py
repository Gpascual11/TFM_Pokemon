#!/usr/bin/env python
"""Minimal test: does a small battle run work in single-process mode?

Run with servers started on port 8000:
    uv run python src/testing_heuristics/1_vs_1/test_minimal.py
"""
import asyncio
import os
import sys
import uuid

# Bootstrap package imports
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_PARENT_DIR = os.path.dirname(_THIS_DIR)
if _PARENT_DIR not in sys.path:
    sys.path.insert(0, _PARENT_DIR)
import importlib
_pkg = os.path.basename(_THIS_DIR)
importlib.import_module(_pkg)
__package__ = _pkg

from poke_env import AccountConfiguration, ServerConfiguration
from poke_env.player import RandomPlayer
from .heuristics.v5 import HeuristicV5


async def main():
    run_id = str(uuid.uuid4())[:4]
    config = ServerConfiguration("ws://127.0.0.1:8000/showdown/websocket", None)

    print("Creating player...", flush=True)
    player = HeuristicV5(
        battle_format="gen9randombattle",
        server_configuration=config,
        max_concurrent_battles=2,
        account_configuration=AccountConfiguration(f"Test_A_{run_id}", None),
    )

    print("Creating opponent...", flush=True)
    opponent = RandomPlayer(
        battle_format="gen9randombattle",
        server_configuration=config,
        max_concurrent_battles=2,
        account_configuration=AccountConfiguration(f"Test_B_{run_id}", None),
    )

    print(f"Starting 5 battles: {player.username} vs {opponent.username}", flush=True)
    await player.battle_against(opponent, n_battles=5)

    print(f"\nDone! Wins: {player.n_won_battles}/5", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
