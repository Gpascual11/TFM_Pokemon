"""Training opponents. Curriculum never uses poke-env SimpleHeuristics as 'v12'."""

from __future__ import annotations

import random
import string

from poke_env.player import MaxBasePowerPlayer, RandomPlayer
from poke_env.ps_client.account_configuration import AccountConfiguration

from .._bootstrap import ensure_src_path
from ..constants import BATTLE_FORMAT

ensure_src_path()

OPPONENT_KEYS = ("random", "maxbp", "v7", "v8", "v11", "v12", "v14")


def _suffix(k: int = 5) -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=k))


def make_opponent(kind: str, *, port: int, rank: int, server_config, suffix: str | None = None):
    """Policy object only (``start_listening=False``). Gym agent2 is the Showdown seat."""
    kind = kind.lower()
    tag = suffix or _suffix()
    kwargs = dict(
        battle_format=BATTLE_FORMAT,
        server_configuration=server_config,
        start_listening=False,
        max_concurrent_battles=1,
    )
    if kind in ("random", "rdm"):
        return RandomPlayer(
            account_configuration=AccountConfiguration(f"Rnd{rank}{tag}", None),
            **kwargs,
        )
    if kind in ("maxbp", "max_power", "mp"):
        return MaxBasePowerPlayer(
            account_configuration=AccountConfiguration(f"Mbp{rank}{tag}", None),
            **kwargs,
        )
    if kind in ("v7", "v8", "v11", "v12", "v14"):
        from p01_heuristics.agents import get_agent_class

        cls = get_agent_class(kind)
        return cls(
            account_configuration=AccountConfiguration(f"{kind}{rank}{tag}", None),
            **kwargs,
        )
    raise ValueError(f"Unknown opponent {kind!r}. Expected one of {OPPONENT_KEYS}.")


def make_eval_player(kind: str, *, server_config, name: str, max_concurrent: int = 4):
    """Live Showdown player (``start_listening=True``) for ``battle_against`` eval."""
    kind = kind.lower()
    kwargs = dict(
        battle_format=BATTLE_FORMAT,
        server_configuration=server_config,
        account_configuration=AccountConfiguration(name, None),
        max_concurrent_battles=max_concurrent,
        start_listening=True,
    )
    if kind in ("random", "rdm"):
        return RandomPlayer(**kwargs)
    if kind in ("maxbp", "max_power", "mp"):
        return MaxBasePowerPlayer(**kwargs)
    from p01_heuristics.agents import get_agent_class

    return get_agent_class(kind)(**kwargs)
