#!/usr/bin/env python
"""Subprocess worker for parallel benchmarking.

This script executes a single mini-batch of Pokémon battles between two
specified agents and streams the results directly to a CSV file. It is designed
to be run as a short-lived process so that the OS reclaims all memory (including
any leaks from LLM background threads) upon exit.
"""

import argparse
import asyncio
import csv
import datetime
import gc
import os
import random
import sys
from pathlib import Path
from typing import Any

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

# Always inject pokechamp fork FIRST so its poke_env overrides site-packages
_POKECHAMP = _ROOT / "pokechamp"
if _POKECHAMP.exists() and str(_POKECHAMP) not in sys.path:
    sys.path.insert(0, str(_POKECHAMP))

from poke_env import AccountConfiguration, ServerConfiguration
import poke_env.environment.battle
from poke_env.environment.battle import Battle
from poke_env.player.player import Player
from poke_env.data import GenData

class StatsBattle(Battle):
    """A Battle subclass that tracks advanced metrics for research analysis."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.voluntary_switches_us = 0
        self.forced_switches_us = 0
        self.voluntary_switches_opp = 0
        self.forced_switches_opp = 0
        self.move_counts_us = {}  # Dict[str, int]
        self.move_counts_opp = {} # Dict[str, int]
        self.crit_count_us = 0
        self.crit_count_opp = 0
        self.miss_count_us = 0
        self.miss_count_opp = 0
        self.supereffective_count_us = 0
        self.supereffective_count_opp = 0

    def switch(self, pokemon_str: str, details: str, hp_status: str):
        identifier = pokemon_str.split(":")[0][:2]
        is_mine = identifier == self._player_role
        
        if is_mine:
            if getattr(self, "force_switch", False):
                self.forced_switches_us += 1
            else:
                self.voluntary_switches_us += 1
        super().switch(pokemon_str, details, hp_status)

    def parse_message(self, split_message):
        if len(split_message) > 3 and split_message[1] == "move":
            pokemon_str = split_message[2]
            move_id = split_message[3]
            identifier = pokemon_str.split(":")[0][:2]
            is_mine = identifier == self._player_role
            
            mid = move_id.lower().replace(" ", "").replace("-", "")
            if is_mine:
                self.move_counts_us[mid] = self.move_counts_us.get(mid, 0) + 1
            else:
                self.move_counts_opp[mid] = self.move_counts_opp.get(mid, 0) + 1
        
        if len(split_message) > 2:
            msg_type = split_message[1]
            if msg_type == "-crit":
                role = getattr(self, "_player_role", "p1") or "p1"
                is_us = split_message[2].startswith(role)
                if is_us:
                    self.crit_count_opp += 1
                else:
                    self.crit_count_us += 1
            elif msg_type == "-miss":
                role = getattr(self, "_player_role", "p1") or "p1"
                is_us = split_message[2].startswith(role)
                if is_us:
                    self.miss_count_us += 1
                else:
                    self.miss_count_opp += 1
            elif msg_type == "-supereffective":
                role = getattr(self, "_player_role", "p1") or "p1"
                is_us = split_message[2].startswith(role)
                if is_us:
                    self.supereffective_count_opp += 1
                else:
                    self.supereffective_count_us += 1
        super().parse_message(split_message)

# Patch the Player class to use our StatsBattle
async def patched_create_battle(self, split_message):
    if split_message[1] == self._format and len(split_message) >= 2:
        battle_tag = "-".join(split_message)[1:]
        if battle_tag in self._battles:
            return self._battles[battle_tag]
        
        gen = GenData.from_format(self._format).gen
        battle = StatsBattle(
            battle_tag=battle_tag,
            username=self.username,
            logger=self.logger,
            gen=gen,
            save_replays=self._save_replays,
        )
        battle._format = self._format
        await self._battle_count_queue.put(None)
        async with self._battle_start_condition:
            self._battle_semaphore.release()
            self._battle_start_condition.notify_all()
            self._battles[battle_tag] = battle
        return battle
    return await self._original_create_battle(split_message)

if not hasattr(Player, "_original_create_battle"):
    Player._original_create_battle = Player._create_battle
    Player._create_battle = patched_create_battle

from p01_heuristics.s01_singles.core.factory import AgentFactory


# ---------------------------------------------------------------------------
# LLM Logging Utils
# ---------------------------------------------------------------------------
def _apply_llm_logging(player: Any, agent_name: str, log_dir: Path, suffix: str = ""):
    """Monkey-patches the LLM player to extract and store chain-of-thought reasonings.

    Args:
        player (Any): The instantiated LLMPlayer instance.
        agent_name (str): Label of the agent (e.g. 'pokechamp').
        log_dir (Path): Base directory for LLM logs.
        suffix (str): Optional suffix to prevent race conditions (e.g. port number).
    """
    if not hasattr(player, "llm"):
        return

    log_dir.mkdir(parents=True, exist_ok=True)
    sfx = f"_{suffix}" if suffix else ""
    thinking_file = log_dir / f"thinking_{agent_name}{sfx}.txt"
    decisions_file = log_dir / f"decisions_{agent_name}{sfx}.txt"

    # Initialize files for this worker session without truncating existing logs
    with open(thinking_file, "a") as f:
        f.write(f"=== {agent_name.upper()} THINKING LOG ===\n\n")
    with open(decisions_file, "a") as f:
        f.write(f"=== {agent_name.upper()} DECISIONS LOG ===\n\n")

    original_get_llm_action = player.llm.get_LLM_action

    def patched_get_llm_action(system_prompt, user_prompt, model, *args, **kwargs):
        output, success, raw_message = original_get_llm_action(system_prompt, user_prompt, model, *args, **kwargs)

        # Extract battle from args or kwargs (index 7 in LLMPlayer.get_LLM_action)
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

        # Clean JSON from decision (aggressive split for Qwen)
        if decision and "{" in decision and "}" in decision:
            import re

            json_match = re.search(r"\{.*\}", decision, re.DOTALL)
            if json_match:
                json_part = json_match.group(0)
                text_before = decision[: json_match.start()].strip()
                if text_before and text_before not in thinking:
                    thinking = f"{thinking}\n\n[From Output]: {text_before}".strip()
                decision = json_part

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
    "safe_one_step": "SOS",
}


def _short(name: str) -> str:
    return _SHORT_NAMES.get(name, name.replace("_", "")[:8])


async def _run_streaming(
    player, opponent, total_n: int, agent_name: str, opp_name: str, out_csv: Path, port: int, battle_format: str = ""
) -> int:
    """Executes battles in small, isolated chunks to optimize memory usage.

    This function cycles through player.battle_against, result extraction,
    and explicit garbage collection (gc.collect()) every 25 games.

    Args:
        player: Primary agent player instance.
        opponent: Opponent player instance.
        total_n (int): Games to play.
        agent_name (str): Label of the primary agent.
        opp_name (str): Label of the opponent.
        out_csv (Path): Where to append the battle data.

    Returns:
        int: Total number of battles finished.
    """
    # Gen 1 battles are prone to infinite loops/hangs; use smaller chunks and tighter timeouts
    is_gen1 = "gen1" in player.battle_format if hasattr(player, "battle_format") else False
    # chunk_size = 10 if is_gen1 else 25
    chunk_size = 25

    # 3 minute timeout for standard chunks, 2 minutes for Gen 1 smaller chunks
    chunk_timeout = 120 if is_gen1 else 180

    done_total = 0

    fieldnames = [
        "battle_id",
        "format",
        "heuristic",
        "opponent",
        "winner",
        "won",
        "turns",
        "fainted_us",
        "remaining_pokemon_us",
        "total_hp_us",
        "fainted_opp",
        "remaining_pokemon_opp",
        "total_hp_opp",
        "team_us",
        "team_opp",
        "side_conditions_us",
        "side_conditions_opp",
        "voluntary_switches_us",
        "forced_switches_us",
        "move_stats_us",
        "move_stats_opp",
        "crit_us",
        "crit_opp",
        "miss_us",
        "miss_opp",
        "supereffective_us",
        "supereffective_opp",
        "hp_perc_us",
        "hp_perc_opp",
        "timestamp",
    ]

    out_csv.parent.mkdir(parents=True, exist_ok=True)

    if not out_csv.exists():
        with open(out_csv, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

    def _format_side_conditions(side_conditions):
        if not side_conditions:
            return ""
        parts = []
        for sc, val in side_conditions.items():
            if hasattr(sc, "name"):
                name = sc.name
            else:
                name = str(sc)
            if val > 1:
                parts.append(f"{name}({val})")
            else:
                parts.append(name)
        return "|".join(sorted(parts))

    def _format_team_detailed(team):
        if not team:
            return ""
        mons = []
        for m in team.values():
            details = [str(m.species)]
            if m.item:
                details.append(f"item:{m.item}")
            if m.ability:
                details.append(f"ability:{m.ability}")
            if m.status:
                # Use .name for enum clean display (FNT, PAR, etc)
                st = m.status.name if hasattr(m.status, "name") else str(m.status)
                details.append(f"status:{st}")
            if m.fainted:
                 details.append("FNT")
            mons.append(f"{m.species}({','.join(details[1:])})")
        return "|".join(sorted(mons))

    for i in range(0, total_n, chunk_size):
        this_n = min(chunk_size, total_n - i)

        # Run battles using poke-env's internal concurrency management
        try:
            # Wrap in timeout to prevent Gen 1 hangs from stalling the whole worker
            await asyncio.wait_for(player.battle_against(opponent, n_battles=this_n), timeout=chunk_timeout)
        except TimeoutError:
            print(f"      ⚠️  Chunk timeout ({chunk_timeout}s) during battle_against. Proceeding with partial results.")
        except Exception as e:
            print(f"      ⚠️  Chunk error during battle_against: {e}")
            # If a chunk fails, we just continue to extract whatever finished

        # Extract results
        rows: list[dict] = []
        # Access internal battles dict directly
        if hasattr(player, "_battles"):
            battles = player._battles
        elif hasattr(player, "battles"):
            # Some versions might have it public
            battles = player.battles # type: ignore
        else:
            battles = {}

        for bid, b in battles.items():
            if not b.finished:
                continue
            row = {
                "battle_id": bid,
                "format": getattr(b, "_format", None) or battle_format,
                "heuristic": agent_name,
                "opponent": opp_name,
                "winner": agent_name if b.won else opp_name,
                "won": 1 if b.won else 0,
                "turns": b.turn,
                "voluntary_switches_us": getattr(b, "voluntary_switches_us", 0),
                "forced_switches_us": getattr(b, "forced_switches_us", 0),
                "crit_us": getattr(b, "crit_count_us", 0),
                "crit_opp": getattr(b, "crit_count_opp", 0),
                "miss_us": getattr(b, "miss_count_us", 0),
                "miss_opp": getattr(b, "miss_count_opp", 0),
                "supereffective_us": getattr(b, "supereffective_count_us", 0),
                "supereffective_opp": getattr(b, "supereffective_count_opp", 0),
                "timestamp": datetime.datetime.now().isoformat(),
            }

            def _serialize_counts(counts):
                if not counts:
                    return ""
                return "|".join([f"{k}:{v}" for k, v in sorted(counts.items(), key=lambda x: x[1], reverse=True)])

            row["move_stats_us"] = _serialize_counts(getattr(b, "move_counts_us", {}))
            row["move_stats_opp"] = _serialize_counts(getattr(b, "move_counts_opp", {}))

            if hasattr(b, "team") and b.team:
                fainted = sum(m.fainted for m in b.team.values())
                row.update(
                    {
                        "fainted_us": fainted,
                        "remaining_pokemon_us": len(b.team) - fainted,
                        "total_hp_us": round(sum(m.current_hp_fraction for m in b.team.values() if not m.fainted), 3),
                        "hp_perc_us": round(sum(m.current_hp_fraction for m in b.team.values()) / len(b.team), 3)
                        if len(b.team) > 0
                        else 0,
                        "team_us": _format_team_detailed(b.team),
                        "side_conditions_us": _format_side_conditions(getattr(b, "side_conditions", {})),
                    }
                )
            if hasattr(b, "opponent_team") and b.opponent_team:
                fainted = sum(m.fainted for m in b.opponent_team.values())
                row.update(
                    {
                        "fainted_opp": fainted,
                        "remaining_pokemon_opp": len(b.opponent_team) - fainted,
                        "total_hp_opp": round(
                            sum(m.current_hp_fraction for m in b.opponent_team.values() if not m.fainted), 3
                        ),
                        "hp_perc_opp": round(sum(m.current_hp_fraction for m in b.opponent_team.values()) / len(b.opponent_team), 3)
                        if len(b.opponent_team) > 0
                        else 0,
                        "team_opp": _format_team_detailed(b.opponent_team),
                        "side_conditions_opp": _format_side_conditions(getattr(b, "opponent_side_conditions", {})),
                    }
                )
            rows.append(row)

        if rows:
            with open(out_csv, "a", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writerows(rows)
            done_total += len(rows)
            print(f"      [DEBUG] Port {port}: Wrote {len(rows)} games to {out_csv.name}", flush=True)

        # IMPORTANT: Clear both player and opponent to free memory
        try:
            player.reset_battles()
            if hasattr(opponent, "reset_battles"):
                opponent.reset_battles()
        except OSError:
            # This happens if some battles timed out and are still technically "running"
            # We log it and continue; the orchestrator will handle missing games
            print("      ⚠️  Could not reset_battles (some still running). Continuing...")

        # Manually clear the local rows and battles references
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
    parser.add_argument("--format", default="gen9randombattle")
    parser.add_argument("--player_backend", default="ollama/qwen3:8b")
    parser.add_argument("--player_prompt_algo", default="io")
    parser.add_argument("--temperature", type=float, default=0.3)
    parser.add_argument("--log-dir", default="./battle_log/pokechamp_benchmark")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    tag = str(random.randint(0, 10_000))
    server_config = ServerConfiguration(f"localhost:{args.port}", None)

    # Create agents using the Unified Factory
    player = AgentFactory.create(
        args.agent,
        account_configuration=AccountConfiguration(f"S{_short(args.agent)}{tag}", ""),
        server_configuration=server_config,
        battle_format=args.format,
        tag=tag,
        backend=args.player_backend,
        prompt_algo=args.player_prompt_algo,
        temperature=args.temperature,
        log_dir=args.log_dir,
        max_concurrent_battles=args.concurrency,
    )

    opponent = AgentFactory.create(
        args.opponent,
        account_configuration=AccountConfiguration(f"Op{_short(args.opponent)}{tag}", ""),
        server_configuration=server_config,
        battle_format=args.format,
        tag=tag,
        backend=args.player_backend,
        prompt_algo=args.player_prompt_algo,
        temperature=args.temperature,
        log_dir=args.log_dir,
        max_concurrent_battles=args.concurrency,
    )

    # Convert output path to absolute BEFORE changing directory
    out_path = Path(args.out).resolve()

    # Always change to pokechamp root because our poke_env fork expects it for data loading
    if _POKECHAMP.exists():
        os.chdir(str(_POKECHAMP))

    # Patch for logging if requested (pokellmon/pokechamp)
    llm_log_dir = _SINGLES / "evaluation" / "results" / "LLM"
    if "pokellmon" in args.agent or "pokechamp" in args.agent:
        _apply_llm_logging(player, args.agent, llm_log_dir, suffix=str(args.port))
    if "pokellmon" in args.opponent or "pokechamp" in args.opponent:
        _apply_llm_logging(opponent, args.opponent, llm_log_dir, suffix=str(args.port))

    total_done = asyncio.run(
        _run_streaming(
            player, opponent, args.n_battles, args.agent, args.opponent, out_path, args.port, battle_format=args.format
        )
    )

    print(f"WORKER_OK:{total_done}")


if __name__ == "__main__":
    main()
