"""Heuristic V1 Doubles — simple max-damage selector for each slot.

Scores each valid order by ``base_power × effectiveness × STAB``,
using the **actual target** in the order (not a maximum across all opponents).
Ally-targeting orders are penalised so we never attack our own side.
"""

from __future__ import annotations

from poke_env.player.battle_order import SingleBattleOrder
from poke_env.battle.move import Move

from ..base import BaseHeuristic2v2

# poke-env target constants (from DoubleBattle)
_OPP1 = 1   # OPPONENT_1_POSITION
_OPP2 = 2   # OPPONENT_2_POSITION
_EMPTY = 0  # spread / no explicit target


class HeuristicV1Doubles(BaseHeuristic2v2):
    """Always select the move with the highest raw damage estimate per slot."""

    def _score_order(self, order: SingleBattleOrder, pokemon, slot: int, battle) -> float:
        action = order.order
        # Switches always score lower than any damage move
        if not isinstance(action, Move):
            return -1.0
        if action.base_power <= 1:
            return 0.0

        target = order.move_target

        # Penalise ally-targeting orders (target < 0 = our own side)
        if target < 0:
            return 0.0

        stab = 1.5 if action.type in pokemon.types else 1.0
        opps = battle.opponent_active_pokemon or []

        if target == _EMPTY:
            # Spread move — score by best opponent effectiveness
            living = [o for o in opps if o is not None]
            if not living:
                return 0.0
            eff = max(o.damage_multiplier(action) for o in living)
        else:
            # Specific opponent target: 1 → index 0, 2 → index 1
            idx = target - 1
            if idx < 0 or idx >= len(opps) or opps[idx] is None:
                return 0.0
            eff = opps[idx].damage_multiplier(action)

        return float(action.base_power * eff * stab)
