#!/usr/bin/env python
"""Subprocess worker for parallel benchmarking.

This script executes a single mini-batch of Pokémon battles between two 
specified agents and streams the results directly to a CSV file. It is designed 
to be run as a short-lived process so that the OS reclaims all memory (including 
any leaks from LLM background threads) upon exit.
"""

import argparse
import asyncio
import os
import sys
import random
import gc
import csv
from pathlib import Path
from typing import Any

from poke_env import AccountConfiguration, ServerConfiguration

# ---------------------------------------------------------------------------
# Package bootstrap
# ---------------------------------------------------------------------------
_DIR = Path(__file__).parent.resolve()
_ENGINE = _DIR
_EVAL = _ENGINE.parent
_SINGLES = _EVAL.parent
_SRC = _SINGLES.parent.parent
_ROOT = _SRC.parent

if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

# Set package context for births
__package__ = "p01_heuristics.s01_singles.evaluation.engine"

from ...core.factory import AgentFactory

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

async def _run_streaming(player, opponent, total_n: int, pc_agent: str, opp_name: str, out_csv: Path) -> int:
    """Run battles in small chunks to prevent memory bloat."""
    chunk_size = 25 
    done_total = 0
    
    fieldnames = [
        "battle_id", "pokechamp_agent", "opponent", "won", "turns",
        "fainted_us", "remaining_pokemon_us", "total_hp_us",
        "fainted_opp", "remaining_pokemon_opp", "total_hp_opp"
    ]
    
    if not out_csv.exists():
        with open(out_csv, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
    
    for i in range(0, total_n, chunk_size):
        this_n = min(chunk_size, total_n - i)
        await player.battle_against(opponent, n_battles=this_n)
        
        # Extract results
        rows: list[dict] = []
        for bid, b in player.battles.items():
            if not b.finished: continue
            row = {
                "battle_id": bid,
                "pokechamp_agent": pc_agent,
                "opponent": opp_name,
                "won": 1 if b.won else 0,
                "turns": b.turn,
            }
            if b.team:
                fainted = sum(m.fainted for m in b.team.values())
                row.update({"fainted_us": fainted, "remaining_pokemon_us": len(b.team) - fainted,
                           "total_hp_us": round(sum(m.current_hp_fraction for m in b.team.values() if not m.fainted), 3)})
            if b.opponent_team:
                fainted = sum(m.fainted for m in b.opponent_team.values())
                row.update({"fainted_opp": fainted, "remaining_pokemon_opp": len(b.opponent_team) - fainted,
                           "total_hp_opp": round(sum(m.current_hp_fraction for m in b.opponent_team.values() if not m.fainted), 3)})
            rows.append(row)

        if rows:
            with open(out_csv, 'a', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writerows(rows)
            done_total += len(rows)
            
        player.battles.clear()
        if hasattr(opponent, 'battles'):
            opponent.battles.clear()
        gc.collect()
        
    return done_total

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pc-agent", required=True)
    parser.add_argument("--opponent", required=True)
    parser.add_argument("--n-battles", type=int, required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--format", default="gen9randombattle")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    tag = str(random.randint(0, 10_000))
    server_config = ServerConfiguration(f"localhost:{args.port}", None)
    
    # Create agents using the Unified Factory
    player = AgentFactory.create(
        args.pc_agent, 
        account_configuration=AccountConfiguration(f"PC{_short(args.pc_agent)}{tag}", None),
        server_configuration=server_config,
        battle_format=args.format,
        tag=tag
    )
    
    opponent = AgentFactory.create(
        args.opponent,
        account_configuration=AccountConfiguration(f"Op{_short(args.opponent)}{tag}", None),
        server_configuration=server_config,
        battle_format=args.format,
        tag=tag,
        max_concurrent_battles=5
    )

    # Change to pokechamp root if needed for LLMs
    if args.pc_agent in AgentFactory.available_llm():
        os.chdir(str(_ROOT / "pokechamp"))
    
    total_done = asyncio.run(_run_streaming(
        player, opponent, args.n_battles, args.pc_agent, args.opponent, Path(args.out)
    ))

    print(f"WORKER_OK:{total_done}")

if __name__ == "__main__":
    main()
