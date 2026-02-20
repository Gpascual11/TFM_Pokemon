"""Shared utilities for 2-vs-2 heuristic strategies.

We centralise stat lookups and the base damage estimator so every heuristic
uses the same canonical formula.
"""

from __future__ import annotations

from poke_env.data import GenData


class GameDataManager:
    """Singleton wrapper for generation-specific game data."""

    _instance: GameDataManager | None = None

    def __init__(self, gen: int = 9) -> None:
        self.data = GenData.from_gen(gen)

    @classmethod
    def instance(cls, gen: int = 9) -> "GameDataManager":
        """Return the module-level singleton, creating it if needed."""
        if cls._instance is None:
            cls._instance = cls(gen)
        return cls._instance


def get_stat(pokemon, stat_name: str) -> int:
    """Return the best available stat value: battle stat → base stat → 100."""
    return (
        pokemon.stats.get(stat_name)
        or pokemon.base_stats.get(stat_name)
        or 100
    )


def get_speed(pokemon, status: str | None = None) -> float:
    """Return effective speed, halved when the Pokémon is paralysed."""
    raw = get_stat(pokemon, "spe")
    return raw * 0.5 if status == "PAR" else float(raw)


def get_status_name(pokemon) -> str:
    """Return the status condition name (e.g. ``'BRN'``) or ``'HEALTHY'``."""
    return pokemon.status.name if pokemon.status else "HEALTHY"


def calculate_base_damage(move, attacker, defender, attacker_status: str) -> float:
    """Estimate move damage using the physical/special stat split.

    Accounts for: atk/def stats, burn penalty on physical moves, STAB, and
    type effectiveness. Does **not** apply spread reduction or random factor.

    :returns: Estimated damage as a float; 0 for non-damaging moves.
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
