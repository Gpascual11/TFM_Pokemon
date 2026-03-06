#!/usr/bin/env python
"""Subprocess worker for parallel doubles benchmarking.

This script executes a single mini-batch of Pokémon battles between two 
specified agents and streams the results directly to a CSV file. It is designed
to be invoked by `benchmark.py` or `benchmark_llm.py` as a standalone process
to ensure memory isolation and parallel execution.
"""

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

# ---------------------------------------------------------------------------
# Package bootstrap
# ---------------------------------------------------------------------------
_DIR = Path(__file__).parent.resolve()
_ENGINE = _DIR
_EVAL = _ENGINE.parent
_DOUBLES = _EVAL.parent
_SRC = _DOUBLES.parent.parent
_ROOT = _SRC.parent

if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

# Always inject pokechamp fork FIRST so its poke_env overrides site-packages
_POKECHAMP = _ROOT / "pokechamp"
if _POKECHAMP.exists() and str(_POKECHAMP) not in sys.path:
    sys.path.insert(0, str(_POKECHAMP))

from poke_env import AccountConfiguration, ServerConfiguration
from p01_heuristics.s02_doubles.core.factory import AgentFactory

# ---------------------------------------------------------------------------
# LLM Logging Utils
# ---------------------------------------------------------------------------
def _apply_llm_logging(player: Any, agent_name: str, log_dir: Path):
    """Monkey-patches the LLM player to extract and store chain-of-thought reasonings."""
    if not hasattr(player, "llm"):
        return

    log_dir.mkdir(parents=True, exist_ok=True)
    thinking_file = log_dir / f"thinking_doubles_{agent_name}.txt"
    decisions_file = log_dir / f"decisions_doubles_{agent_name}.txt"
    
    with open(thinking_file, "a") as f:
        f.write(f"\n\n=== NEW BATCH: {agent_name.upper()} ===\n")
    with open(decisions_file, "a") as f:
        f.write(f"\n\n=== NEW BATCH: {agent_name.upper()} ===\n")

    original_get_llm_action = player.llm.get_LLM_action

    def patched_get_llm_action(system_prompt, user_prompt, model, *args, **kwargs):
        output, success, raw_message = original_get_llm_action(system_prompt, user_prompt, model, *args, **kwargs)
        
        battle = kwargs.get("battle")
        if not battle and len(args) >= 7:
             battle = args[6]
        
        turn = battle.turn if hasattr(battle, "turn") else "N/A"
        thinking = ""
        decision = raw_message
        
        if raw_message:
            if "THINKING: " in raw_message and "\n\nRESPONSE: " in raw_message:
                parts = raw_message.split("\n\nRESPONSE: ")
                thinking = parts[0].replace("THINKING: ", "").strip()
                decision = parts[1].strip()
            elif "THINKING: " in raw_message:
                thinking = raw_message.replace("THINKING: ", "").strip()

        if success:
            with open(thinking_file, "a") as f:
                f.write(f"--- Turn {turn} ---\n{thinking}\n\n")
            with open(decisions_file, "a") as f:
                f.write(f"--- Turn {turn} ---\n{decision}\n\n")
            
        return output, success, raw_message

    player.llm.get_LLM_action = patched_get_llm_action

_SHORT_NAMES: dict[str, str] = {
    "simple_heuristic": "SH",
    "max_power": "MP",
    "pokechamp": "PC",
    "pokellmon": "PL",
    "one_step": "OS",
    "abyssal": "AB",
    "random": "RD",
    "vgc": "VG",
}

def _short(name: str) -> str:
    return _SHORT_NAMES.get(name, name.replace("_", "")[:8])

async def _run_streaming(player, opponent, total_n: int, agent_name: str, opp_name: str, out_csv: Path) -> int:
    """Executes battles in small, isolated chunks to optimize memory usage (RAM safety)."""
    chunk_size = 25 
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
                "battle_id": bid, "heuristic": agent_name, "opponent": opp_name,
                "won": 1 if b.won else 0, "turns": b.turn,
            }
            if b.team:
                f = sum(m.fainted for m in b.team.values())
                row.update({"fainted_us": f, "remaining_pokemon_us": len(b.team) - f,
                           "total_hp_us": round(sum(m.current_hp_fraction for m in b.team.values() if not m.fainted), 3)})
            if b.opponent_team:
                f = sum(m.fainted for m in b.opponent_team.values())
                row.update({"fainted_opp": f, "remaining_pokemon_opp": len(b.opponent_team) - f,
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
        del rows
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

    logging.basicConfig(level=logging.INFO, format=f"[worker:{args.port}] %(levelname)s %(message)s")

    tag = str(random.randint(0, 10_000))
    server_config = ServerConfiguration(f"localhost:{args.port}", None)
    
    player = AgentFactory.create(
        args.agent, account_configuration=AccountConfiguration(f"D{_short(args.agent)}{tag}", None),
        server_configuration=server_config, battle_format=args.format, max_concurrent_battles=args.concurrency
    )
    
    opponent = AgentFactory.create(
        args.opponent, account_configuration=AccountConfiguration(f"DOp{_short(args.opponent)}{tag}", None),
        server_configuration=server_config, battle_format=args.format, max_concurrent_battles=args.concurrency
    )

    if _POKECHAMP.exists():
        os.chdir(str(_POKECHAMP))
    
    llm_log_dir = _DOUBLES / "results" / "LLM"
    if "pokellmon" in args.agent or "pokechamp" in args.agent or "vgc" in args.agent:
        _apply_llm_logging(player, args.agent, llm_log_dir)
    if "pokellmon" in args.opponent or "pokechamp" in args.opponent or "vgc" in args.opponent:
        _apply_llm_logging(opponent, args.opponent, llm_log_dir)
    
    total_done = asyncio.run(_run_streaming(
        player, opponent, args.n_battles, args.agent, args.opponent, Path(args.out)
    ))
    print(f"WORKER_OK:{total_done}")

if __name__ == "__main__":
    main()
