"""Shared utilities for all 1-vs-1 heuristic strategies.

Centralises stat lookups and the base damage estimator so that every
heuristic version uses the same canonical implementation.
"""

from __future__ import annotations

from poke_env.data import GenData


class GameDataManager:
    """Singleton wrapper for generation-specific game data.

    Avoids reloading ``GenData`` on every use.
    """

    _instance: GameDataManager | None = None

    def __init__(self, gen: int = 9) -> None:
        self.data = GenData.from_gen(gen)

    @classmethod
    def instance(cls, gen: int = 9) -> GameDataManager:
        """Return the module-level singleton."""
        if cls._instance is None:
            cls._instance = cls(gen)
        return cls._instance


def get_stat(pokemon, stat_name: str) -> int:
    """Return the best available stat value for *pokemon*.

    Falls back through: battle stat → base stat → 100 (neutral default).
    """
    return (
        pokemon.stats.get(stat_name)
        or pokemon.base_stats.get(stat_name)
        or 100
    )


def get_speed(pokemon, status: str | None = None) -> float:
    """Return effective speed, halved when paralysed."""
    raw = get_stat(pokemon, "spe")
    return raw * 0.5 if status == "PAR" else float(raw)


def get_status_name(pokemon) -> str:
    """Return the status condition name (e.g. ``'BRN'``) or ``'HEALTHY'``."""
    return pokemon.status.name if pokemon.status else "HEALTHY"


def calculate_base_damage(
    move,
    attacker,
    defender,
    attacker_status: str,
) -> float:
    """Estimate move damage using the physical/special split.

    Factors: attack / defence stats, burn penalty on physical moves,
    STAB (same-type attack bonus), and type effectiveness.

    Used by V2 and V4.  V1 has its own simpler formula; V5 extends
    this with weather and terrain modifiers.
    """
    if move.base_power <= 1:
        return 0.0

    if move.category.name == "PHYSICAL":
        atk = get_stat(attacker, "atk") * (0.5 if attacker_status == "BRN" else 1.0)
        defe = get_stat(defender, "def")
    else:
        atk = get_stat(attacker, "spa")
        defe = get_stat(defender, "spd")

    effectiveness = defender.damage_multiplier(move)
    stab = 1.5 if move.type in attacker.types else 1.0

    return float((atk / defe) * move.base_power * effectiveness * stab)
