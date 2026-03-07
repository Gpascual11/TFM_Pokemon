#!/usr/bin/env python
"""Small debug runner for pokechamp LLM agents (single-process).

This is a lightweight alternative to the full parallel benchmark. It runs a few
single battles with turn-level progress so you can validate:

- Showdown server connectivity
- pokechamp repo import/data-path correctness
- LLM backend settings (ollama/gemini/etc.)

Typical usage (after starting a server on port 8000):

    uv run python src/p01_heuristics/s01_singles/evaluation/debug/debug_runner.py \\
        --backend ollama/qwen3:8b --format gen9randombattle

(engine/debug_runner.py is a shim that forwards to this module.)
"""

from __future__ import annotations

import argparse
import asyncio
import os
import time
from pathlib import Path
import sys

# ---------------------------------------------------------------------------
# Package bootstrap — allow running this file directly via `python .../debug_runner.py`
# ---------------------------------------------------------------------------
_DIR = Path(__file__).parent.resolve()
_SRC = _DIR.parent.parent.parent.parent  # src/
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from poke_env import AccountConfiguration, ServerConfiguration

from p01_heuristics.s01_singles.core.factory import AgentFactory


async def _run_single(
    agent: str,
    opponent: str,
    backend: str,
    battle_format: str,
    prompt_algo: str,
    temperature: float,
    port: int,
) -> None:
    """Run a single battle and print a concise summary."""
    tag = "DBG"
    server_config = ServerConfiguration(f"localhost:{port}", None)

    print(f"\n=== {agent} (backend={backend}) vs {opponent} — format={battle_format} ===")
    start = time.time()

    player = AgentFactory.create(
        agent,
        account_configuration=AccountConfiguration(f"DBG{agent[:6]}{tag}", None),
        server_configuration=server_config,
        battle_format=battle_format,
        backend=backend,
        prompt_algo=prompt_algo,
        temperature=temperature,
        log_dir="./battle_log/debug_runner",
    )
    opp = AgentFactory.create(
        opponent,
        account_configuration=AccountConfiguration(f"DBG{opponent[:6]}{tag}", None),
        server_configuration=server_config,
        battle_format=battle_format,
        backend=backend,
        prompt_algo=prompt_algo,
        temperature=temperature,
        log_dir="./battle_log/debug_runner",
    )

    # Progress monitor: print current turn every few seconds while the game runs.
    async def monitor_turns():
        last_turn = -1
        # Wait until a battle object exists
        while not player.battles:
            await asyncio.sleep(1.0)
        battle = next(iter(player.battles.values()))
        while not battle.finished:
            if battle.turn != last_turn:
                last_turn = battle.turn
                print(f"    [{agent} vs {opponent}] turn={battle.turn}")
            await asyncio.sleep(2.0)

    await asyncio.gather(
        player.battle_against(opp, n_battles=1),
        monitor_turns(),
    )

    elapsed = time.time() - start
    # There should be exactly one finished battle on player side.
    battle = next(iter(player.battles.values()))
    print(
        f"    Finished battle {battle.battle_tag}: "
        f"turns={battle.turn}, won={bool(battle.won)}, "
        f"duration={elapsed:.1f}s"
    )


async def main() -> None:
    """Run a small sequence of tests."""
    parser = argparse.ArgumentParser(description="Run a few debug battles with LLM agents.")
    parser.add_argument("--backend", default="ollama/qwen3:8b")
    parser.add_argument("--prompt-algo", default="io")
    parser.add_argument("--temperature", type=float, default=0.3)
    parser.add_argument("--format", default="gen9randombattle")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    # Ensure pokechamp's relative data paths resolve if the repo exists.
    root = Path(__file__).resolve().parents[5]
    pokechamp_root = root / "pokechamp"
    if pokechamp_root.exists():
        os.chdir(str(pokechamp_root))

    await _run_single("pokellmon", "random", args.backend, args.format, args.prompt_algo, args.temperature, args.port)
    await _run_single("pokechamp", "random", args.backend, args.format, args.prompt_algo, args.temperature, args.port)
    await _run_single("pokellmon", "pokechamp", args.backend, args.format, args.prompt_algo, args.temperature, args.port)


if __name__ == "__main__":
    asyncio.run(main())

