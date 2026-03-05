#!/usr/bin/env python
"""Benchmark for comparing Pokechamp and Pokellmon with thinking/decision logging.

Matchups:
1. pokechamp vs simple_heuristic
2. pokellmon vs simple_heuristic

Logs thinking and decisions to separate files.
"""

from __future__ import annotations

import asyncio
import os
import time
import json
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

__package__ = "p01_heuristics.s01_singles.s01_pokechamp"

from poke_env import ServerConfiguration
from ._worker import _create_player, _create_opponent

def _apply_logging_patch(player: Any, agent_name: str):
    """Monkey-patch the LLM backend to log thinking and decisions."""
    if not hasattr(player, "llm"):
        print(f"⚠️  Player {agent_name} has no 'llm' attribute, skipping patch.")
        return

    original_get_llm_action = player.llm.get_LLM_action
    
    thinking_file = f"thinking_{agent_name}.txt"
    decisions_file = f"decisions_{agent_name}.txt"
    
    # Clear files at start
    with open(thinking_file, "w") as f:
        f.write(f"=== {agent_name.upper()} THINKING LOG ===\n\n")
    with open(decisions_file, "w") as f:
        f.write(f"=== {agent_name.upper()} DECISIONS LOG ===\n\n")

    def patched_get_llm_action(system_prompt, user_prompt, model, *args, **kwargs):
        # The original call might have many positional arguments from LLMPlayer
        output, success, raw_message = original_get_llm_action(system_prompt, user_prompt, model, *args, **kwargs)
        
        # Extract battle from args or kwargs (it's at index 7 in the positional args passed by LLMPlayer)
        battle = kwargs.get("battle")
        if not battle and len(args) >= 7:
             battle = args[6] if len(args) > 6 else None
        
        turn = battle.turn if hasattr(battle, "turn") else "N/A"
        
        thinking = ""
        decision = raw_message
        
        # 1. Try to extract from our structured format (THINKING: ... RESPONSE: ...)
        if raw_message:
            if "THINKING: " in raw_message and "\n\nRESPONSE: " in raw_message:
                parts = raw_message.split("\n\nRESPONSE: ")
                thinking = parts[0].replace("THINKING: ", "").strip()
                decision = parts[1].strip()
            elif "THINKING: " in raw_message:
                thinking = raw_message.replace("THINKING: ", "").strip()
            
        # 2. If decision is empty or null, fallback to raw message
        if not decision or decision == "null" or decision == "":
             decision = raw_message

        # 3. Clean decision for the log by removing known thinking parts or keys
        try:
            if output:
                # Use regex to find the actual JSON object to avoid "Extra data" errors
                # We use a non-greedy Match to find the first complete object
                import re
                json_match = re.search(r'(\{.*?\})', output, re.DOTALL)
                json_str = json_match.group(1) if json_match else output
                
                try:
                    parsed_json = json.loads(json_str)
                except:
                    # If non-greedy failed (e.g. nested), try greedy but clean up
                    json_match = re.search(r'(\{.*\})', output, re.DOTALL)
                    json_str = json_match.group(1) if json_match else output
                    parsed_json = json.loads(json_str)

                if not thinking and "thought" in parsed_json:
                    thinking = parsed_json["thought"]
                
                # If the decision is the whole JSON, clean it for the decision file
                if isinstance(parsed_json, dict):
                    clean_decision = {k: v for k, v in parsed_json.items() if k != "thought"}
                    if clean_decision:
                        decision = json.dumps(clean_decision)
        except:
             # If all parsing fails, just keep the raw decision string
             pass

        # Final check: if decision is exactly the same as thinking, or empty, use raw_message
        if not decision or decision == thinking:
            decision = raw_message

        # Aggressive split for Qwen 3.5: if decision contains JSON, extract just the JSON
        if decision and "{" in decision and "}" in decision:
            import re
            json_match = re.search(r'\{.*\}', decision, re.DOTALL)
            if json_match:
                json_part = json_match.group(0)
                # If there was text before the JSON, move it to thinking
                text_before = decision[:json_match.start()].strip()
                if text_before and text_before not in thinking:
                    thinking = f"{thinking}\n\n[From Output]: {text_before}".strip()
                decision = json_part

        # Only log if we successfully found an action (avoid redundant/failed slots)
        if success:
            with open(thinking_file, "a") as f:
                f.write(f"--- Turn {turn} ---\n{thinking}\n\n")
            with open(decisions_file, "a") as f:
                f.write(f"--- Turn {turn} ---\n{decision}\n\n")
            
        return output, success, raw_message

    player.llm.get_LLM_action = patched_get_llm_action
    print(f"✅ Applied logging patch to {agent_name} (Logging to {thinking_file} and {decisions_file})")

async def _run_comparison_matchup(
    pc_agent: str,
    opponent: str,
    backend: str,
    battle_format: str = "gen9randombattle",
) -> None:
    # Use different tags with some randomness to avoid "name taken" error on the Showdown server
    import random
    tag = f"C_{pc_agent[:3]}_{random.randint(100, 999)}" 
    server_config = ServerConfiguration("localhost:8000", None)

    print(f"\n⚔️  MATCHUP: {pc_agent} vs {opponent} (1 battle)...")
    start = time.time()

    player = _create_player(
        pc_agent,
        server_config,
        battle_format,
        tag,
        backend=backend,
        log_dir="./battle_log/comparison",
    )
    
    # Apply the logging patch
    _apply_logging_patch(player, pc_agent)
    
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
            await asyncio.sleep(1.0)

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
    """Run the comparison benchmark sequence."""
    os.chdir(str(_POKECHAMP_ROOT))
    
    # Check if user wants a different backend
    # Updated to 'simple_heuristic' and qwen3.5:4b as requested by the user
    # Increased context window is now handled in OllamaPlayer
    backend = os.environ.get("LLM_BACKEND", "ollama/qwen3.5:4b")
    
    target_opponent = "simple_heuristic"
    
    print(f"🚀 Starting LLM Comparison Benchmark ({backend})")
    print("=" * 60)
    print(f"Comparing 'pokechamp' vs 'pokellmon' against {target_opponent}")

    # 1) pokechamp vs simple_heuristic
    await _run_comparison_matchup("pokechamp", target_opponent, backend)

    # 2) pokellmon vs simple_heuristic
    await _run_comparison_matchup("pokellmon", target_opponent, backend)
    
    print("\n" + "=" * 60)
    print("🎉 Comparison Benchmark Complete!")
    print("Results saved to:")
    print(" - thinking_pokechamp.txt / decisions_pokechamp.txt")
    print(" - thinking_pokellmon.txt / decisions_pokellmon.txt")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n🛑 Benchmark stopped by user.")
        sys.exit(0)
