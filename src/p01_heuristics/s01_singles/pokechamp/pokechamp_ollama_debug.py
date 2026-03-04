#!/usr/bin/env python
"""Small debug runner for local Ollama-based pokechamp agents.

Runs three short test battles with detailed progress so you can see that the
model is working and how long each game takes:

1. pokellmon (LLM) vs random (rule-based)
2. pokechamp (LLM) vs random (rule-based)
3. pokellmon (LLM) vs pokechamp (LLM)

It uses the same bootstrap logic as ``benchmark.py`` / ``_worker.py`` and the
same backend string you would pass via ``--player_backend``, but runs everything
in a single process and prints per-battle summaries.
"""

from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path
import sys

from typing import Any

# ---------------------------------------------------------------------------
# Package bootstrap — mirror _worker.py / benchmark.py
# ---------------------------------------------------------------------------
_DIR = Path(__file__).parent.resolve()
_SRC = _DIR.parent.parent.parent
_POKECHAMP_ROOT = _SRC.parent / "pokechamp"
if str(_POKECHAMP_ROOT) not in sys.path:
    sys.path.insert(0, str(_POKECHAMP_ROOT))
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

__package__ = "p01_heuristics.s01_singles.pokechamp"

from poke_env import ServerConfiguration  # type: ignore[import-untyped]

from ._worker import _create_player, _create_opponent  # type: ignore[import-untyped]


async def _run_single(
    pc_agent: str,
    opponent: str,
    backend: str,
    battle_format: str = "gen9randombattle",
    prompt_algo: str = "io",
    temperature: float = 0.3,
) -> None:
    """Run a single battle and print a concise summary."""
    tag = "DBG"
    server_config = ServerConfiguration("localhost:8000", None)

    print(f"\n=== {pc_agent} (backend={backend}) vs {opponent} — format={battle_format} ===")
    start = time.time()

    player = _create_player(
        pc_agent,
        server_config,
        battle_format,
        tag,
        backend=backend,
        prompt_algo=prompt_algo,
        temperature=temperature,
        log_dir="./battle_log",
    )
    opp = _create_opponent(opponent, server_config, battle_format, tag)

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
                print(f"    [{pc_agent} vs {opponent}] turn={battle.turn}")
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
    """Run a small sequence of local Ollama tests."""
    # Ensure pokechamp's relative data paths (poke_env/data/static/...) resolve
    # correctly by running from the pokechamp repo root, just like _worker does.
    os.chdir(str(_POKECHAMP_ROOT))

    # Adjust this to match the Ollama model you pulled.
    backend = "ollama/qwen3:8b"
    battle_format = "gen9randombattle"

    # 1) pokellmon vs random (LLM vs baseline)
    await _run_single("pokellmon", "random", backend, battle_format)

    # 2) pokechamp vs random (LLM vs baseline)
    await _run_single("pokechamp", "random", backend, battle_format)

    # 3) pokellmon vs pokechamp (LLM vs LLM)
    await _run_single("pokellmon", "pokechamp", backend, battle_format)


if __name__ == "__main__":
    asyncio.run(main())

