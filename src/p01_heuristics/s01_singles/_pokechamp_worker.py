#!/usr/bin/env python
"""Subprocess worker for :mod:`pokechamp_benchmark`.

Runs a single mini-batch of *N* battles between a Pokechamp agent and an
opponent, writes per-battle results to a CSV, and **exits**.  The process
exit guarantees that the OS reclaims all memory held by pokechamp's
``POKE_LOOP`` background thread.

This script is never called directly — it is spawned by
``pokechamp_benchmark.run_matchup`` via :func:`subprocess.run`.
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import Any

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

# ---------------------------------------------------------------------------
# Package bootstrap — must mirror pokechamp_benchmark.py exactly.
# ---------------------------------------------------------------------------
_DIR = Path(__file__).parent.resolve()
_SRC = _DIR.parent.parent
_POKECHAMP_ROOT = _SRC.parent / "pokechamp"
if str(_POKECHAMP_ROOT) not in sys.path:
    sys.path.insert(0, str(_POKECHAMP_ROOT))
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

__package__ = "p01_heuristics.s01_singles"

from poke_env import AccountConfiguration, ServerConfiguration  # noqa: E402
from poke_env.player import RandomPlayer  # noqa: E402
from poke_env.player.baselines import AbyssalPlayer, MaxBasePowerPlayer, OneStepPlayer  # noqa: E402
from poke_env.player.team_util import get_llm_player  # noqa: E402

from .core.factory import HeuristicFactory  # noqa: E402

# ---------------------------------------------------------------------------
# Username abbreviations (Showdown enforces an 18-char limit)
# ---------------------------------------------------------------------------
_SHORT_NAMES: dict[str, str] = {
    "simple_heuristic": "SH",
    "max_power": "MP",
    "pokechamp": "PC",
    "pokellmon": "PL",
    "one_step": "OS",
    "abyssal": "AB",
    "random": "RD",
}


def _short(name: str) -> str:
    """Return a ≤8-char abbreviation for *name*."""
    return _SHORT_NAMES.get(name, name.replace("_", "")[:8])


# ---------------------------------------------------------------------------
# Player factories
# ---------------------------------------------------------------------------
def _create_player(
    agent_name: str,
    server_config: ServerConfiguration,
    battle_format: str,
    tag: str,
    *,
    backend: str = "",
    prompt_algo: str = "io",
    temperature: float = 0.3,
    log_dir: str = "./battle_log",
    concurrent: int = 5,
):
    """Instantiate a Pokechamp-side player.

    Rule-based agents are created directly with the shared
    *server_config*.  LLM agents go through ``get_llm_player``.

    Parameters
    ----------
    agent_name : str
        One of ``random``, ``max_power``, ``abyssal``, ``one_step``,
        ``pokechamp``, or ``pokellmon``.
    server_config : ServerConfiguration
        Connection details for the local Showdown instance.
    battle_format : str
        Pokémon Showdown battle format string.
    tag : str
        Random numeric suffix appended to the username.
    backend, prompt_algo, temperature, log_dir :
        Forwarded to ``get_llm_player`` for LLM agents.
    concurrent : int
        Maximum simultaneous battles.
    """
    kw: dict[str, Any] = {
        "battle_format": battle_format,
        "server_configuration": server_config,
        "max_concurrent_battles": concurrent,
    }
    acct = AccountConfiguration(f"PC{_short(agent_name)}{tag}", None)

    if agent_name == "random":
        return RandomPlayer(account_configuration=acct, **kw)
    if agent_name == "max_power":
        return MaxBasePowerPlayer(account_configuration=acct, **kw)
    if agent_name == "abyssal":
        return AbyssalPlayer(account_configuration=acct, **kw)
    if agent_name == "one_step":
        return OneStepPlayer(account_configuration=acct, **kw)

    ns = argparse.Namespace(temperature=temperature, log_dir=log_dir)
    return get_llm_player(
        ns,
        backend=backend,
        prompt_algo=prompt_algo,
        name=agent_name,
        battle_format=battle_format,
        PNUMBER1=tag,
        use_timeout=False,
    )


def _create_opponent(
    opponent_name: str,
    server_config: ServerConfiguration,
    battle_format: str,
    tag: str,
    concurrent: int = 5,
):
    """Instantiate an opponent (heuristic v1–v6 or poke_env baseline).

    Parameters
    ----------
    opponent_name : str
        Heuristic version (``v1``–``v6``) or baseline
        (``random``, ``max_power``, ``simple_heuristic``).
    server_config : ServerConfiguration
        Shared connection details.
    battle_format : str
        Pokémon Showdown battle format string.
    tag : str
        Random numeric suffix for the username.
    concurrent : int
        Maximum simultaneous battles.

    Raises
    ------
    ValueError
        If *opponent_name* is not recognised.
    """
    kw: dict[str, Any] = {
        "battle_format": battle_format,
        "server_configuration": server_config,
        "max_concurrent_battles": concurrent,
    }
    acct = AccountConfiguration(f"Op{_short(opponent_name)}{tag}", None)

    if opponent_name in HeuristicFactory.available_versions():
        return HeuristicFactory.create(opponent_name, account_configuration=acct, **kw)
    if opponent_name == "max_power":
        return MaxBasePowerPlayer(account_configuration=acct, **kw)
    if opponent_name == "simple_heuristic":
        return AbyssalPlayer(account_configuration=acct, **kw)
    if opponent_name == "random":
        return RandomPlayer(account_configuration=acct, **kw)

    raise ValueError(f"Unknown opponent: {opponent_name}")


# ---------------------------------------------------------------------------
# Battle execution
# ---------------------------------------------------------------------------
async def _run(player, opponent, n: int) -> None:
    """Execute *n* battles between *player* and *opponent*."""
    await player.battle_against(opponent, n_battles=n)


def _extract_battle_rows(player, pc_agent: str, opponent: str) -> list[dict]:
    """Convert finished battles on *player* into flat dicts for CSV export.

    Returns one dict per finished battle with keys: ``battle_id``,
    ``pokechamp_agent``, ``opponent``, ``won``, ``turns``, plus optional
    team-level stats (``fainted_us``, ``total_hp_us``, etc.).
    """
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


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main() -> None:
    """Parse CLI arguments, run battles, write CSV, and exit."""
    parser = argparse.ArgumentParser(description="Single-batch pokechamp worker")
    parser.add_argument("--pc-agent", required=True, help="Pokechamp agent identifier.")
    parser.add_argument("--opponent", required=True, help="Opponent identifier.")
    parser.add_argument("--n-battles", type=int, required=True, help="Battles to play.")
    parser.add_argument("--port", type=int, required=True, help="Showdown server port.")
    parser.add_argument("--format", default="gen9randombattle", help="Battle format.")
    parser.add_argument("--backend", default="", help="LLM backend (if applicable).")
    parser.add_argument("--prompt-algo", default="io", help="LLM prompt algorithm.")
    parser.add_argument("--temperature", type=float, default=0.3, help="LLM temperature.")
    parser.add_argument("--log-dir", default="./battle_log", help="Battle log directory.")
    parser.add_argument("--out", required=True, help="Absolute path for the output CSV.")
    args = parser.parse_args()

    tag = str(np.random.randint(0, 10_000))
    server_config = ServerConfiguration(f"localhost:{args.port}", None)

    player = _create_player(
        args.pc_agent,
        server_config,
        args.format,
        tag,
        backend=args.backend,
        prompt_algo=args.prompt_algo,
        temperature=args.temperature,
        log_dir=args.log_dir,
    )
    opponent = _create_opponent(args.opponent, server_config, args.format, tag)

    os.chdir(str(_POKECHAMP_ROOT))
    asyncio.run(_run(player, opponent, args.n_battles))

    rows = _extract_battle_rows(player, args.pc_agent, args.opponent)

    if rows:
        pd.DataFrame(rows).to_csv(args.out, index=False)
        print(f"WORKER_OK:{len(rows)}")
    else:
        print("WORKER_OK:0")


if __name__ == "__main__":
    main()
