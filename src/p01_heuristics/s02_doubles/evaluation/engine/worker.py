#!/usr/bin/env python
"""Subprocess worker for parallel doubles benchmarking."""

import argparse
import asyncio
import os
import sys
import random
import gc
import csv
import logging
from pathlib import Path
from typing import Any

# Bootstrap path for imports
_DIR = Path(__file__).parent.resolve()
_ROOT = _DIR.parent.parent.parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from poke_env import AccountConfiguration, ServerConfiguration

# Package bootstrap
_DIR = Path(__file__).parent.resolve()
_ENGINE = _DIR
_EVAL = _ENGINE.parent
_DOUBLES = _EVAL.parent
_SRC = _DOUBLES.parent.parent
_ROOT = _SRC.parent

from p01_heuristics.s02_doubles.core.factory import AgentFactory

def _short(name: str) -> str:
    return name.replace("_", "")[:8]

async def _run_streaming(player, opponent, total_n: int, agent_name: str, opp_name: str, out_csv: Path) -> int:
    chunk_size = 100 # Increased chunk size for faster batching
    done_total = 0
    
    fieldnames = [
        "battle_id", "heuristic", "opponent", "won", "turns",
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
        
        rows: list[dict] = []
        for bid, b in player.battles.items():
            if not b.finished: continue
            row = {
                "battle_id": bid,
                "heuristic": agent_name,
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
            
        player.reset_battles()
        if hasattr(opponent, 'reset_battles'):
            opponent.reset_battles()
        gc.collect()
        
    return done_total

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent", required=True)
    parser.add_argument("--opponent", required=True)
    parser.add_argument("--n-battles", type=int, required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--format", default="gen9randomdoublesbattle")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    # Basic logging config
    logging.basicConfig(level=logging.INFO, format=f"[worker:{args.port}] %(levelname)s %(message)s")

    tag = str(random.randint(0, 10_000))
    server_config = ServerConfiguration(f"ws://127.0.0.1:{args.port}/showdown/websocket", None)
    
    try:
        player = AgentFactory.create(
            args.agent, 
            account_configuration=AccountConfiguration(f"D{_short(args.agent)}{tag}", None),
            server_configuration=server_config,
            battle_format=args.format,
            max_concurrent_battles=args.concurrency
        )
        
        opponent = AgentFactory.create(
            args.opponent,
            account_configuration=AccountConfiguration(f"DOp{_short(args.opponent)}{tag}", None),
            server_configuration=server_config,
            battle_format=args.format,
            max_concurrent_battles=args.concurrency
        )

        # Change to pokechamp root if needed for LLM agents
        if args.agent in AgentFactory.available_llm():
             os.chdir(str(_ROOT / "pokechamp"))

        total_done = asyncio.run(_run_streaming(
            player, opponent, args.n_battles, args.agent, args.opponent, Path(args.out)
        ))

        print(f"WORKER_OK:{total_done}")
    except Exception as e:
        logging.exception(f"Worker failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
