#!/usr/bin/env python
"""Subprocess worker for :mod:`benchmark_parallel`.

Identical to _worker.py but renamed to follow the parallel naming convention.
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import Any

import csv
import gc
import random
# import numpy as np  # Removed to save RAM
# import pandas as pd # Removed to save RAM

# ---------------------------------------------------------------------------
# Package bootstrap
# ---------------------------------------------------------------------------
_DIR = Path(__file__).parent.resolve()
_SRC = _DIR.parent.parent.parent
_POKECHAMP_ROOT = _SRC.parent / "pokechamp"

if str(_POKECHAMP_ROOT) not in sys.path:
    sys.path.insert(0, str(_POKECHAMP_ROOT))
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

__package__ = "p01_heuristics.s01_singles.s01_pokechamp"

from .true_simple_heuristic import TrueSimpleHeuristicsPlayer
from poke_env import AccountConfiguration, ServerConfiguration
from poke_env.player import RandomPlayer
from poke_env.player.baselines import AbyssalPlayer, MaxBasePowerPlayer

from ..core.factory import HeuristicFactory
from .safe_one_step_player import SafeOneStepPlayer

_SHORT_NAMES: dict[str, str] = {
    "simple_heuristic": "SH",
    "max_power": "MP",
    "pokechamp": "PC",
    "pokellmon": "PL",
    "one_step": "OS",
    "abyssal": "AB",
    "random": "RD",
    "safe_one_step": "SOS",
}

def _short(name: str) -> str:
    return _SHORT_NAMES.get(name, name.replace("_", "")[:8])

def _create_player(
    agent_name: str,
    server_config: ServerConfiguration,
    battle_format: str,
    tag: str,
    concurrent: int = 5,
):
    base_kw: dict[str, Any] = {
        "battle_format": battle_format,
        "server_configuration": server_config,
    }
    acct = AccountConfiguration(f"PC{_short(agent_name)}{tag}", None)

    if agent_name == "random":
        return RandomPlayer(account_configuration=acct, **base_kw)
    if agent_name == "max_power":
        return MaxBasePowerPlayer(account_configuration=acct, **base_kw)
    if agent_name == "abyssal":
        return AbyssalPlayer(account_configuration=acct, **base_kw)
    if agent_name == "one_step":
        return SafeOneStepPlayer(account_configuration=acct, **base_kw)
    if agent_name == "simple_heuristic":
        return TrueSimpleHeuristicsPlayer(account_configuration=acct, **base_kw)
    if agent_name == "safe_one_step":
        return SafeOneStepPlayer(account_configuration=acct, **base_kw)

    raise ValueError(f"Unknown agent: {agent_name}")

def _create_opponent(
    opponent_name: str,
    server_config: ServerConfiguration,
    battle_format: str,
    tag: str,
    concurrent: int = 5,
):
    base_kw: dict[str, Any] = {
        "battle_format": battle_format,
        "server_configuration": server_config,
    }
    kw: dict[str, Any] = {
        **base_kw,
        "max_concurrent_battles": concurrent,
    }
    acct = AccountConfiguration(f"Op{_short(opponent_name)}{tag}", None)

    if opponent_name in HeuristicFactory.available_versions():
        return HeuristicFactory.create(opponent_name, account_configuration=acct, **kw)
    if opponent_name == "max_power":
        return MaxBasePowerPlayer(account_configuration=acct, **base_kw)
    if opponent_name == "simple_heuristic":
        return TrueSimpleHeuristicsPlayer(account_configuration=acct, **base_kw)
    if opponent_name == "abyssal":
        return AbyssalPlayer(account_configuration=acct, **base_kw)
    if opponent_name == "one_step":
        return SafeOneStepPlayer(account_configuration=acct, **base_kw)
    if opponent_name == "safe_one_step":
        return SafeOneStepPlayer(account_configuration=acct, **base_kw)
    if opponent_name == "random":
        return RandomPlayer(account_configuration=acct, **base_kw)

    raise ValueError(f"Unknown opponent: {opponent_name}")

async def _run_streaming(player, opponent, total_n: int, pc_agent: str, opp_name: str, out_csv: Path) -> int:
    """Run battles in small chunks, appending to CSV and clearing memory."""
    chunk_size = 25 
    done_total = 0
    
    # Define CSV columns
    fieldnames = [
        "battle_id", "pokechamp_agent", "opponent", "won", "turns",
        "fainted_us", "remaining_pokemon_us", "total_hp_us",
        "fainted_opp", "remaining_pokemon_opp", "total_hp_opp"
    ]
    
    # Initialize CSV if not exists
    if not out_csv.exists():
        with open(out_csv, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
    
    for i in range(0, total_n, chunk_size):
        this_n = min(chunk_size, total_n - i)
        await player.battle_against(opponent, n_battles=this_n)
        
        rows = _extract_battle_rows(player, pc_agent, opp_name)
        if rows:
            with open(out_csv, 'a', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writerows(rows)
            done_total += len(rows)
            
        # IMPORTANT: Clear both player and opponent to free memory
        player.battles.clear()
        if hasattr(opponent, 'battles'):
            opponent.battles.clear()
            
        # Explicitly collect garbage to ensure memory release
        gc.collect()
        
    return done_total

def _extract_battle_rows(player, pc_agent: str, opponent: str) -> list[dict]:
    rows: list[dict] = []
    for bid, b in player.battles.items():
        if not b.finished:
            continue
        row: dict[str, Any] = {
            "battle_id": bid,
            "pokechamp_agent": pc_agent,
            "opponent": opponent,
            "won": 1 if b.won else 0,
            "turns": b.turn,
        }
        if b.team:
            fainted_us = sum(m.fainted for m in b.team.values())
            row["fainted_us"] = fainted_us
            row["remaining_pokemon_us"] = len(b.team) - fainted_us
            row["total_hp_us"] = round(
                sum(m.current_hp_fraction for m in b.team.values() if not m.fainted),
                3,
            )
        if b.opponent_team:
            fainted_opp = sum(m.fainted for m in b.opponent_team.values())
            row["fainted_opp"] = fainted_opp
            row["remaining_pokemon_opp"] = len(b.opponent_team) - fainted_opp
            row["total_hp_opp"] = round(
                sum(m.current_hp_fraction for m in b.opponent_team.values() if not m.fainted),
                3,
            )
        rows.append(row)
    return rows

def main() -> None:
    parser = argparse.ArgumentParser(description="Parallel pokechamp worker")
    parser.add_argument("--pc-agent", required=True)
    parser.add_argument("--opponent", required=True)
    parser.add_argument("--n-battles", type=int, required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--format", default="gen9randombattle")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    tag = str(random.randint(0, 10_000))
    server_config = ServerConfiguration(f"localhost:{args.port}", None)

    player = _create_player(
        args.pc_agent,
        server_config,
        args.format,
        tag,
    )
    opponent = _create_opponent(args.opponent, server_config, args.format, tag)

    os.chdir(str(_POKECHAMP_ROOT))
    
    # Run and stream results directly to CSV
    total_done = asyncio.run(_run_streaming(
        player, opponent, args.n_battles, args.pc_agent, args.opponent, Path(args.out)
    ))

    print(f"WORKER_OK:{total_done}")

if __name__ == "__main__":
    main()
