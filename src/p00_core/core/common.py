"""Common utility functions for singles heuristic players.

This module provides shared mathematical and game-state evaluation tools
used by various heuristic agents (e.g., V2, V3, V6). By centralizing
these calculations, we ensure consistent baseline damage estimation,
status handling, and speed tie breaking across different agent versions.

It relies heavily on the `poke_env` data structures for execution.
"""

from __future__ import annotations

from poke_env.data import GenData


class GameDataManager:
    """Singleton wrapper for generation-specific game data.

    Loading Pokémon data via `GenData.from_gen(gen)` involves reading large
    JSON files into memory. In a parallel benchmarking environment with thousands
    of battles, doing this per-agent or per-battle causes severe memory bloat
    and CPU overhead. This singleton ensures the data is loaded exactly once
    per Python process, keeping memory consumption flat.
    """

    _instance: GameDataManager | None = None

    def __init__(self, gen: int = 9) -> None:
        self.data = GenData.from_gen(gen)

    @classmethod
    def instance(cls, gen: int = 9) -> GameDataManager:
        """Return the module-level singleton instance."""
        if cls._instance is None:
            cls._instance = cls(gen)
        return cls._instance


def get_stat(pokemon, stat_name: str) -> int:
    """Return the best available stat value for a given Pokémon.

    This function attempts to retrieve the most accurate stat representation
    for the current battle state. It uses a fallback mechanism:
    1. Battle Stat (`pokemon.stats`): The actual computed stat in battle, if known.
    2. Base Stat (`pokemon.base_stats`): The Pokédex base stat, if the battle stat is unknown.
    3. Default (100): A neutral fallback value to prevent division by zero or evaluation errors.

    Args:
        pokemon (Pokemon): The `poke_env` Pokémon object to evaluate.
        stat_name (str): The short name of the stat (e.g., "atk", "def", "spe").

    Returns:
        int: The estimated or actual integer value of the requested stat.
    """
    if pokemon.stats and pokemon.stats.get(stat_name):
        return pokemon.stats[stat_name]
    if pokemon.base_stats and pokemon.base_stats.get(stat_name):
        return pokemon.base_stats[stat_name]
    return 100


def get_speed(pokemon, status: str | None = None) -> float:
    """Calculate the effective speed of a Pokémon, factoring in major status conditions.

    In Pokémon mechanics, Paralysis (PAR) cuts the affected Pokémon's speed in half
    (in modern generations). This heuristic applies that penalty to ensure agents
    correctly evaluate speed ties and turn orders.

    Args:
        pokemon (Pokemon): The `poke_env` Pokémon object.
        status (str | None): The string representation of the Pokémon's status condition.

    Returns:
        float: The effective speed stat, potentially halved if paralyzed.
    """
    raw = get_stat(pokemon, "spe")
    return raw * 0.5 if status == "PAR" else float(raw)


def get_status_name(pokemon) -> str:
    """Normalize the Pokémon's status condition into a safe string.

    When checking conditions, a healthy Pokémon returns `None` for its status
    in `poke_env`. This helper normalizes `None` to ``'HEALTHY'`` to simplify
    string comparisons and dictionary lookups in heuristic logic downstream.
    """
    return pokemon.status.name if pokemon.status else "HEALTHY"


def calculate_base_damage(
    move,
    attacker,
    defender,
    attacker_status: str,
) -> float:
    """Estimate the raw damage output of a move against a specific defender.

    This function provides a fast, standardized heuristic for move scoring. It ignores
    complex mechanics like random damage rolls, exact levels, and specific items to
    prioritize execution speed during wide heuristic evaluations.

    The formula used is a simplified proportional estimator:
    `Damage = (Attack / Defense) * Base Power * Effectiveness * STAB`

    Implementation details:
    - Differentiates between PHYSICAL and SPECIAL moves to use the correct offensive/defensive stats.
    - Applies the Burn (BRN) penalty, which halves the effective Attack for Physical moves.
    - Calculates STAB (Same-Type Attack Bonus) granting a 1.5x multiplier if types match.
    - Retrieves exact type effectiveness multipliers (e.g., 2x, 0.5x, 0x) directly from `poke_env`.

    Returns:
        float: A numeric score representing the estimated damage. Returns 0.0 for status moves
        or moves with no base power.
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
