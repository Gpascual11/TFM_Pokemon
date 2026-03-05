#!/usr/bin/env python
"""Light benchmark for Pokechamp vs Heuristics with turn monitoring.

Specific matchups:
1. pokechamp (LLM) vs simple_heuristic (Rule-based)
2. pokechamp (LLM) vs abyssal (Rule-based)

Uses Ollama with qwen3:8b for the LLM backend.
"""

from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path
import sys
from typing import Any

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

__package__ = "p01_heuristics.s01_singles.pokechamp"

from poke_env import ServerConfiguration
from ._worker import _create_player, _create_opponent

async def _run_single_matchup(
    pc_agent: str,
    opponent: str,
    backend: str,
    battle_format: str = "gen9randombattle",
) -> None:
    """Run a single battle and print live turn updates."""
    tag = "LIGHT"
    server_config = ServerConfiguration("localhost:8000", None)

    print(f"\n⚔️  MATCHUP: {pc_agent} vs {opponent} (1 battle)...")
    start = time.time()

    player = _create_player(
        pc_agent,
        server_config,
        battle_format,
        tag,
        backend=backend,
        log_dir="./battle_log/light_benchmark",
    )
    opp = _create_opponent(opponent, server_config, battle_format, tag)

    async def monitor_turns():
        last_turn = -1
        # Wait for battle to start
        while not player.battles:
            await asyncio.sleep(0.5)
        
        battle = next(iter(player.battles.values()))
        while not battle.finished:
            if battle.turn != last_turn:
                last_turn = battle.turn
                elapsed = time.time() - start
                print(f"    [Turn {battle.turn}] {pc_agent} vs {opponent} | Elapsed: {elapsed:.0f}s", flush=True)
            await asyncio.sleep(2.0)

    try:
        await asyncio.gather(
            player.battle_against(opp, n_battles=1),
            monitor_turns(),
        )
    except Exception as e:
        print(f"❌ Error during matchup: {e}")
        return

    elapsed = time.time() - start
    battle = next(iter(player.battles.values()))
    result = "WON" if battle.won else "LOST"
    print(f"\n✅ MATCHUP FINISHED: {result}")
    print(f"   Total Turns: {battle.turn}")
    print(f"   Duration: {elapsed:.1f}s")


async def main() -> None:
    """Run the light benchmark sequence."""
    os.chdir(str(_POKECHAMP_ROOT))
    
    backend = "ollama/qwen3:8b"
    print("🚀 Starting Light Benchmark (qwen3:8b)")
    print("=" * 60)

    # 1) pokechamp vs simple_heuristic
    await _run_single_matchup("pokechamp", "simple_heuristic", backend)

    # 2) pokechamp vs abyssal
    await _run_single_matchup("pokechamp", "abyssal", backend)
    
    print("\n" + "=" * 60)
    print("🎉 Light Benchmark Complete!")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n🛑 Benchmark stopped by user.")
        sys.exit(0)
