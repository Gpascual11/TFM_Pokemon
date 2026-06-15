#!/usr/bin/env python
# ruff: noqa: E402, E501, I001
"""Online Bot Runner for testing Heuristic Agents on the public Pokémon Showdown server."""

import argparse
import asyncio
import csv
import datetime
import json
import logging
import os
import signal
import sys
from pathlib import Path

# Graceful shutdown handler
SHUTDOWN_REQUESTED = False
ACTIVE_AGENT = None


def sigint_handler(signum, frame):
    global SHUTDOWN_REQUESTED
    SHUTDOWN_REQUESTED = True

    # Check if there are active battles
    has_active_battle = False
    if ACTIVE_AGENT is not None:
        has_active_battle = any(not b.finished for b in ACTIVE_AGENT.battles.values())

    if not has_active_battle:
        print("\n👋 No active battles. Exiting immediately.")
        sys.exit(0)
    else:
        print(
            "\n⚠️  [Interrupt] Shutdown requested! The bot will exit after the current battle finishes to avoid forfeiting."
        )


# Register the SIGINT signal handler
signal.signal(signal.SIGINT, sigint_handler)

# Bootstrap the package path
_THIS_DIR = Path(__file__).parent.resolve()
_EVAL_DIR = _THIS_DIR.parent
_S01_DIR = _EVAL_DIR.parent
_P01_DIR = _S01_DIR.parent
_SRC_DIR = _P01_DIR.parent
_ROOT_DIR = _SRC_DIR.parent

if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

# Inject pokechamp fork ONLY for pokechamp-based agents that need LocalSim.
# Heuristic agents v1-v14 use standard poke-env 0.11.0 — no injection needed.
# Injecting unconditionally triggers: baselines.py → LocalSim → GPTPlayer → openai
_POKECHAMP_AGENTS = {"pokechamp", "pokellmon", "abyssal", "max_power", "one_step"}
_POKECHAMP = _ROOT_DIR / "pokechamp"

# Parse agent argument early to determine if we need the pokechamp fork
# before importing poke_env
agent_name = "v12"
for arg in sys.argv:
    if arg.startswith("--agent="):
        agent_name = arg.split("=", 1)[1]
        break
else:
    for i, arg in enumerate(sys.argv):
        if arg == "--agent" and i + 1 < len(sys.argv):
            agent_name = sys.argv[i+1]
            break

if agent_name in _POKECHAMP_AGENTS and _POKECHAMP.exists() and str(_POKECHAMP) not in sys.path:
    sys.path.insert(0, str(_POKECHAMP))

from poke_env import AccountConfiguration, ServerConfiguration
from p01_heuristics.s01_singles.agents import get_agent_class
from poke_env.player.player import Player
from poke_env.data import GenData

try:
    from poke_env.environment.battle import Battle
except ModuleNotFoundError:
    from poke_env.battle import Battle


class StatsBattle(Battle):
    """A Battle subclass that tracks advanced metrics for research analysis."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.voluntary_switches_us = 0
        self.forced_switches_us = 0
        self.voluntary_switches_opp = 0
        self.forced_switches_opp = 0
        self.move_counts_us = {}  # Dict[str, int]
        self.move_counts_opp = {}  # Dict[str, int]
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
        else:
            if self.opponent_active_pokemon is None:
                self.voluntary_switches_opp += 1
            elif self.opponent_active_pokemon.fainted:
                self.forced_switches_opp += 1
            else:
                self.voluntary_switches_opp += 1
        super().switch(pokemon_str, details, hp_status)

    def parse_message(self, split_message):
        # Normalize the player role username case to prevent battle mapping errors
        if len(split_message) > 3 and split_message[1] == "player":
            _, username = split_message[2], split_message[3]
            if username.lower() == self.player_username.lower() and username != self.player_username:
                self.player_username = username

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
        try:
            super().parse_message(split_message)
        except RuntimeError as e:
            if "Invalid player message" in str(e):
                # Safely ignore Showdown's transient empty player messages
                pass
            else:
                raise


# Patch the Player class to use our StatsBattle
async def patched_create_battle(self, split_message):
    format_str = split_message[1]
    is_valid_format = format_str == self._format or (
        format_str.startswith("gen")
        and "randombattle" in format_str
        and "doubles" not in format_str
        and "blitz" not in format_str
    )
    if is_valid_format and len(split_message) >= 2:
        battle_tag = "-".join(split_message)[1:]
        if battle_tag in self._battles:
            return self._battles[battle_tag]

        try:
            gen = GenData.from_format(format_str).gen
        except Exception:
            gen = 9
        battle = StatsBattle(
            battle_tag=battle_tag,
            username=self.username,
            logger=self.logger,
            gen=gen,
            save_replays=self._save_replays,
        )
        battle._format = format_str
        await self._battle_count_queue.put(None)
        async with self._battle_start_condition:
            self._battle_semaphore.release()
            self._battle_start_condition.notify_all()
            self._battles[battle_tag] = battle
        if self._start_timer_on_battle_start:
            await self.ps_client.send_message("/timer on", battle.battle_tag)
        return battle
    return await self._original_create_battle(split_message)


if not hasattr(Player, "_original_create_battle"):
    Player._original_create_battle = Player._create_battle
    Player._create_battle = patched_create_battle

# Configuration for official Smogon server
if hasattr(ServerConfiguration, "_fields") and "websocket_url" in ServerConfiguration._fields:
    OFFICIAL_SERVER = ServerConfiguration(
        "wss://sim3.psim.us/showdown/websocket",
        "https://play.pokemonshowdown.com/action.php"
    )
else:
    OFFICIAL_SERVER = ServerConfiguration(
        "sim3.psim.us",
        "https://play.pokemonshowdown.com/action.php"
    )


# State and History Files
# Default to a repo-relative location so the script is portable across machines
# (the previous hardcoded /home/sirp/... path only worked on one computer).
# Overridable per-run via --log-dir or the TFM_LOG_DIR env var (set in main()).
_DEFAULT_LOG_DIR = _ROOT_DIR / "data" / "1_vs_1" / "logs"
STATE_FILE = _DEFAULT_LOG_DIR / "online_bot_state.json"
HISTORY_FILE = _DEFAULT_LOG_DIR / "battle_history.csv"
LOGGED_BATTLES = set()


def load_logged_battles():
    """Populate LOGGED_BATTLES from the existing history CSV.

    The dedup set lives only in memory, so without this a restart mid-week would
    re-log any finished battle still held in the agent's battle dict. Reading the
    persisted CSV on startup makes logging idempotent across stop/resume cycles.
    """
    if not HISTORY_FILE.exists():
        return
    try:
        with open(HISTORY_FILE, newline="") as f:
            for row in csv.DictReader(f):
                bid = row.get("battle_id")
                if bid:
                    LOGGED_BATTLES.add(bid)
    except Exception:
        pass


def save_state(agent_name, battle_format, target_games, games_played):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    state = {"agent": agent_name, "format": battle_format, "target_games": target_games, "games_played": games_played}
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=4)


def load_state(agent_name, battle_format):
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE) as f:
                state = json.load(f)
            if state.get("agent") == agent_name and state.get("format") == battle_format:
                return state
        except Exception:
            pass
    return None


def clear_state():
    if STATE_FILE.exists():
        try:
            STATE_FILE.unlink()
        except Exception:
            pass


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
            st = m.status.name if hasattr(m.status, "name") else str(m.status)
            details.append(f"status:{st}")
        if m.fainted:
            details.append("FNT")
        mons.append(f"{m.species}({','.join(details[1:])})")
    return "|".join(sorted(mons))


def _serialize_counts(counts):
    if not counts:
        return ""
    return "|".join([f"{k}:{v}" for k, v in sorted(counts.items(), key=lambda x: x[1], reverse=True)])


def log_battle(battle, agent_name, agent):
    if battle.battle_tag in LOGGED_BATTLES:
        return

    if battle.won and battle.turn < 6:
        return

    file_exists = HISTORY_FILE.exists()
    fieldnames = [
        "battle_id",
        "format",
        "heuristic",
        "opponent",
        "winner",
        "won",
        "turns",
        "rating_us",
        "rating_opp",
        "decisions_us",
        "decisions_opp",
        "fallback_moves_us",
        "fallback_moves_opp",
        "error_moves_us",
        "error_moves_opp",
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
        "voluntary_switches_opp",
        "forced_switches_opp",
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
        "hazard_sets_us",
        "hazard_sets_opp",
        "hazard_removals_us",
        "hazard_removals_opp",
        "setup_uses_us",
        "setup_uses_opp",
        "ko_checks_us",
        "ko_checks_opp",
        "matchup_switches_us",
        "matchup_switches_opp",
        "terastallized_us",
        "terastallized_opp",
        "timestamp",
    ]

    opp_name = battle.opponent_username if hasattr(battle, "opponent_username") else "Unknown"

    row = {
        "battle_id": battle.battle_tag,
        "format": getattr(battle, "_format", ""),
        "heuristic": agent_name,
        "opponent": opp_name,
        "winner": agent_name if battle.won else opp_name,
        "won": 1 if battle.won else 0,
        "turns": battle.turn,
        # Ladder Elo at the time of this battle — the primary metric vs humans.
        # poke-env exposes these on the Battle once Showdown sends the |rated| /
        # rating messages; default to "" when unrated (e.g. accept-challenge mode).
        "rating_us": getattr(battle, "rating", "") or "",
        "rating_opp": getattr(battle, "opponent_rating", "") or "",
        "decisions_us": getattr(agent, "_total_decisions_by_battle", {}).get(battle.battle_tag, 0),
        "decisions_opp": 0,
        "fallback_moves_us": getattr(agent, "_fallback_moves_by_battle", {}).get(battle.battle_tag, 0),
        "fallback_moves_opp": 0,
        "error_moves_us": getattr(agent, "_error_moves_by_battle", {}).get(battle.battle_tag, 0),
        "error_moves_opp": 0,
        "voluntary_switches_us": getattr(battle, "voluntary_switches_us", 0),
        "forced_switches_us": getattr(battle, "forced_switches_us", 0),
        "voluntary_switches_opp": getattr(battle, "voluntary_switches_opp", 0),
        "forced_switches_opp": getattr(battle, "forced_switches_opp", 0),
        "crit_us": getattr(battle, "crit_count_us", 0),
        "crit_opp": getattr(battle, "crit_count_opp", 0),
        "miss_us": getattr(battle, "miss_count_us", 0),
        "miss_opp": getattr(battle, "miss_count_opp", 0),
        "supereffective_us": getattr(battle, "supereffective_count_us", 0),
        "supereffective_opp": getattr(battle, "supereffective_count_opp", 0),
        # Strategy tracking
        "hazard_sets_us": getattr(agent, "_hazard_sets_by_battle", {}).get(battle.battle_tag, 0),
        "hazard_sets_opp": 0,
        "hazard_removals_us": getattr(agent, "_hazard_removals_by_battle", {}).get(battle.battle_tag, 0),
        "hazard_removals_opp": 0,
        "setup_uses_us": getattr(agent, "_setup_uses_by_battle", {}).get(battle.battle_tag, 0),
        "setup_uses_opp": 0,
        "ko_checks_us": getattr(agent, "_ko_checks_by_battle", {}).get(battle.battle_tag, 0),
        "ko_checks_opp": 0,
        "matchup_switches_us": getattr(agent, "_matchup_switches_by_battle", {}).get(battle.battle_tag, 0),
        "matchup_switches_opp": 0,
        "terastallized_us": 1
        if hasattr(battle, "team") and battle.team and any(getattr(mon, "is_terastallized", False) for mon in battle.team.values())
        else 0,
        "terastallized_opp": 1
        if hasattr(battle, "opponent_team")
        and battle.opponent_team
        and any(getattr(mon, "is_terastallized", False) for mon in battle.opponent_team.values())
        else 0,
        "timestamp": datetime.datetime.now().isoformat(),
    }

    row["move_stats_us"] = _serialize_counts(getattr(battle, "move_counts_us", {}))
    row["move_stats_opp"] = _serialize_counts(getattr(battle, "move_counts_opp", {}))

    if hasattr(battle, "team") and battle.team:
        fainted = sum(mon.fainted for mon in battle.team.values())
        row.update(
            {
                "fainted_us": fainted,
                "remaining_pokemon_us": len(battle.team) - fainted,
                "total_hp_us": round(
                    sum(mon.current_hp_fraction for mon in battle.team.values() if not mon.fainted), 3
                ),
                "hp_perc_us": round(sum(mon.current_hp_fraction for mon in battle.team.values()) / len(battle.team), 3)
                if len(battle.team) > 0
                else 0,
                "team_us": _format_team_detailed(battle.team),
                "side_conditions_us": _format_side_conditions(getattr(battle, "side_conditions", {})),
            }
        )
    if hasattr(battle, "opponent_team") and battle.opponent_team:
        fainted = sum(mon.fainted for mon in battle.opponent_team.values())
        row.update(
            {
                "fainted_opp": fainted,
                "remaining_pokemon_opp": len(battle.opponent_team) - fainted,
                "total_hp_opp": round(
                    sum(mon.current_hp_fraction for mon in battle.opponent_team.values() if not mon.fainted), 3
                ),
                "hp_perc_opp": round(
                    sum(mon.current_hp_fraction for mon in battle.opponent_team.values()) / len(battle.opponent_team), 3
                )
                if len(battle.opponent_team) > 0
                else 0,
                "team_opp": _format_team_detailed(battle.opponent_team),
                "side_conditions_opp": _format_side_conditions(getattr(battle, "opponent_side_conditions", {})),
            }
        )

    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(HISTORY_FILE, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)

    LOGGED_BATTLES.add(battle.battle_tag)


class ChallengeAcceptingPlayer:
    """A wrapper to run any agent in a passive 'online and accept challenges' mode."""

    def __init__(self, agent):
        self.agent = agent

    async def run(self):
        print(f"🤖 Bot '{self.agent.username}' is online and listening for challenges...")
        while True:
            # Sit and wait. poke-env handles challenges in the background
            # if we use the player's internal listener or run it asynchronously.
            await asyncio.sleep(1)


async def main():
    # Always change to pokechamp root because our poke_env fork expects it for data loading
    if _POKECHAMP.exists():
        os.chdir(str(_POKECHAMP))

    parser = argparse.ArgumentParser(description="Run a Showdown Bot on the official Smogon server.")
    parser.add_argument("--agent", type=str, default="v12", help="Heuristic agent version to run (default: v12)")
    parser.add_argument("--username", type=str, required=True, help="Registered Pokémon Showdown username")
    parser.add_argument(
        "--password", type=str, help="Password for your registered username (can also set SHOWDOWN_PASSWORD env var)"
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["ladder", "accept"],
        default="accept",
        help="Run mode: 'ladder' to play public matches, 'accept' to wait and accept friend challenges (default: accept)",
    )
    parser.add_argument(
        "--format", type=str, default="gen9randombattle", help="Showdown battle format (default: gen9randombattle)"
    )
    parser.add_argument("--games", type=int, default=10, help="Number of games to play in ladder mode (default: 10)")
    parser.add_argument(
        "--concurrency", type=int, default=1, help="Max number of concurrent battles to play in parallel (default: 1)"
    )
    parser.add_argument(
        "--log-dir",
        type=str,
        default=None,
        help="Directory for state/history logs. Defaults to <repo>/data/1_vs_1/logs_<agent> "
        "(override with this flag or the TFM_LOG_DIR env var).",
    )
    args = parser.parse_args()

    global STATE_FILE, HISTORY_FILE
    # Portable, per-agent log directory. Precedence: --log-dir > TFM_LOG_DIR env >
    # repo-relative default. All runs of the same agent share one appending CSV.
    if args.log_dir:
        log_dir = Path(args.log_dir).expanduser()
    elif os.environ.get("TFM_LOG_DIR"):
        log_dir = Path(os.environ["TFM_LOG_DIR"]).expanduser() / f"logs_{args.agent}"
    else:
        log_dir = _ROOT_DIR / "data" / "1_vs_1" / f"logs_{args.agent}"
    STATE_FILE = log_dir / "online_bot_state.json"
    HISTORY_FILE = log_dir / "battle_history.csv"
    log_dir.mkdir(parents=True, exist_ok=True)
    # Enable per-turn decision logging for the agent (one JSONL per battle under
    # <log_dir>/decisions/). Must be set BEFORE the agent is instantiated, since
    # BaseHeuristic1v1 reads this env var in __init__.
    os.environ["TFM_DECISION_LOG_DIR"] = str(log_dir / "decisions")
    # Seed the in-memory dedup set from any prior CSV so stop/resume never
    # double-logs a battle across separate runs during the week.
    load_logged_battles()

    # Get password from arguments or environment variable
    password = args.password or os.environ.get("SHOWDOWN_PASSWORD")
    if not password:
        print(
            "⚠️  Warning: No password provided. Running unauthenticated (challenges only, cannot register or play ladder)."
        )

    # Configure account and server
    account_config = AccountConfiguration(args.username, password)

    # Instantiate the agent class dynamically
    try:
        AgentCls = get_agent_class(args.agent)
    except ValueError as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

    # Ensure logs directory exists
    log_dir.mkdir(parents=True, exist_ok=True)

    # Configure logging to save to a file as well as the console
    logger = logging.getLogger(args.username)
    logger.setLevel(logging.INFO)
    file_handler = logging.FileHandler(log_dir / "online_bot.log")
    file_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    logger.addHandler(file_handler)

    print(f"Initializing {args.agent} agent...")

    # Instantiate player
    agent = AgentCls(
        server_configuration=OFFICIAL_SERVER,
        account_configuration=account_config,
        save_replays=str(log_dir / "replays"),
        battle_format=args.format,
        max_concurrent_battles=args.concurrency,
        start_timer_on_battle_start=True,
    )

    # Patch to accept challenges for any gen1-9 random battle
    def is_valid_challenge_format(fmt_str: str) -> bool:
        return (
            fmt_str.startswith("gen")
            and "randombattle" in fmt_str
            and "doubles" not in fmt_str
            and "blitz" not in fmt_str
        )

    async def patched_handle_challenge_request(self, split_message):
        challenging_player = split_message[2].strip()
        if challenging_player != self.username:
            if len(split_message) >= 6:
                fmt = split_message[5]
                if fmt == self._format or is_valid_challenge_format(fmt):
                    await self._challenge_queue.put(challenging_player)

    async def patched_update_challenges(self, split_message):
        self.logger.debug("Updating challenges with %s", split_message)
        challenges = json.loads(split_message[2]).get("challengesFrom", {})
        for user, fmt in challenges.items():
            if fmt == self._format or is_valid_challenge_format(fmt):
                await self._challenge_queue.put(user)

    import types

    agent._handle_challenge_request = types.MethodType(patched_handle_challenge_request, agent)
    agent._update_challenges = types.MethodType(patched_update_challenges, agent)
    agent.ps_client._handle_challenge_request = agent._handle_challenge_request
    agent.ps_client._update_challenges = agent._update_challenges

    # Patch ps_client to normalize username on successful login (case-insensitive correction)
    original_handle_message = agent.ps_client._handle_message

    async def patched_handle_message(self, message: str):
        for line in message.split("\n"):
            parts = line.split("|")
            if len(parts) > 2 and parts[1] == "updateuser":
                raw_username = parts[2].strip()
                if not raw_username.startswith("Guest "):
                    cleaned = raw_username
                    while cleaned and cleaned[0] in "+%@*&~!★☆":
                        cleaned = cleaned[1:]
                    if cleaned.lower() == self.username.lower() and cleaned != self.username:
                        from poke_env import AccountConfiguration

                        new_config = AccountConfiguration(cleaned, self._account_configuration.password)
                        self._account_configuration = new_config
                        if hasattr(agent, "_account_configuration"):
                            agent._account_configuration = new_config
                        self.logger.info(
                            f"Dynamically normalized client username casing from {self.username} to {cleaned}"
                        )
        await original_handle_message(message)

    agent.ps_client._handle_message = types.MethodType(patched_handle_message, agent.ps_client)

    # Patch agent.ladder to respect SIGINT / SHUTDOWN_REQUESTED
    async def patched_ladder(self, n_games: int):
        from poke_env.concurrency import handle_threaded_coroutines
        await handle_threaded_coroutines(self._patched_ladder(n_games))

    async def _patched_ladder(self, n_games: int):
        from time import perf_counter
        await self.ps_client.logged_in.wait()
        start_time = perf_counter()

        for _ in range(n_games):
            if SHUTDOWN_REQUESTED:
                break
            async with self._battle_start_condition:
                await self.ps_client.search_ladder_game(self._format, self.next_team)
                await self._battle_start_condition.wait()
                while self._battle_count_queue.full():
                    async with self._battle_end_condition:
                        await self._battle_end_condition.wait()
                await self._battle_semaphore.acquire()
        await self._battle_count_queue.join()
        self.logger.info(
            "Laddering finished in %fs",
            perf_counter() - start_time,
        )

    agent.ladder = types.MethodType(patched_ladder, agent)
    agent._patched_ladder = types.MethodType(_patched_ladder, agent)

    global ACTIVE_AGENT
    ACTIVE_AGENT = agent

    if args.mode == "ladder":
        if not password:
            print("❌ Error: You must provide a password to log in and play on the public ladder.")
            sys.exit(1)

        # Try to load previous state to resume
        state = load_state(args.agent, args.format)
        if state:
            completed = state["games_played"]
            total = state["target_games"]
            print(f"🔄 Resuming previous session: {completed}/{total} games completed.")
            games_to_play = total - completed
            games_played_offset = completed
        else:
            total = args.games
            games_to_play = total
            games_played_offset = 0
            save_state(args.agent, args.format, total, 0)

        print(f"🚀 Playing {games_to_play} ladder games in {args.format} (Total target: {total})...")

        # Periodically log finished battles and update state in the background
        async def log_watcher():
            while not SHUTDOWN_REQUESTED:
                finished_count = len([
                    b for b in agent.battles.values() 
                    if b.finished and not (b.won and b.turn < 6)
                ])
                current_game_num = min(games_played_offset + finished_count, total)
                save_state(args.agent, args.format, total, current_game_num)

                for battle in list(agent.battles.values()):
                    if battle.finished:
                        log_battle(battle, args.agent, agent)
                await asyncio.sleep(5)

        watcher_task = asyncio.create_task(log_watcher())

        try:
            while not SHUTDOWN_REQUESTED:
                state = load_state(args.agent, args.format)
                completed = state["games_played"] if state else games_played_offset
                if completed >= total:
                    break
                games_to_play = total - completed
                games_played_offset = completed
                print(f"🎮 Starting batch of {games_to_play} ladder games...")
                await agent.ladder(games_to_play)
        except Exception as e:
            print(f"❌ Ladder run failed: {e}")
        finally:
            watcher_task.cancel()
            # Log final state and any remaining battles on exit
            finished_count = len([
                b for b in agent.battles.values() 
                if b.finished and not (b.won and b.turn < 6)
            ])
            current_game_num = min(games_played_offset + finished_count, total)
            save_state(args.agent, args.format, total, current_game_num)
            for battle in list(agent.battles.values()):
                if battle.finished:
                    log_battle(battle, args.agent, agent)

        # Check if we finished all games
        final_state = load_state(args.agent, args.format)
        if final_state and final_state["games_played"] >= final_state["target_games"]:
            print("✅ All scheduled games completed successfully.")
            clear_state()
        elif final_state:
            print(
                f"⚠️ Session paused. Run the script again to resume the remaining {total - final_state['games_played']} games."
            )

    elif args.mode == "accept":
        # Periodically log any finished battles in the background
        async def log_watcher():
            while not SHUTDOWN_REQUESTED:
                for battle in list(agent.battles.values()):
                    if battle.finished:
                        log_battle(battle, args.agent, agent)
                await asyncio.sleep(5)

        watcher_task = asyncio.create_task(log_watcher())

        print(f"🟢 Bot logged in as {args.username}.")
        print("To battle the bot, open Pokémon Showdown, search for your bot's username, and send a challenge.")
        try:
            # We run the agent's internal listener to accept one challenge at a time in a loop
            # so that we check the SHUTDOWN_REQUESTED flag after each challenge finishes.
            while not SHUTDOWN_REQUESTED:
                await agent.accept_challenges(opponent=None, n_challenges=1)
        except (KeyboardInterrupt, asyncio.CancelledError):
            print("\nShutting down bot.")
        finally:
            watcher_task.cancel()
            # Log one last time on exit
            for battle in list(agent.battles.values()):
                if battle.finished:
                    log_battle(battle, args.agent, agent)


if __name__ == "__main__":
    # Run the async loop
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot stopped by user.")
