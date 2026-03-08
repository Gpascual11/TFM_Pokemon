from __future__ import annotations

"""Simple doubles baseline player used as `simple_heuristic` in s02_doubles.

This avoids depending on pokechamp's forked poke-env baselines
(`SimpleHeuristicsPlayer`) while providing a reasonable 2v2 reference bot.

Logic:
- Inherits the doubles orchestration from `BaseHeuristic2v2`.
- Scores only damaging moves, using the shared `calculate_base_damage` helper
  against all living opponents.
- Penalises ally-targeting and non-damaging moves.
"""

from poke_env.player.battle_order import SingleBattleOrder
from poke_env.battle.move import Move

from ..core.base import BaseHeuristic2v2
from ..core.common import calculate_base_damage, get_status_name


_OPP1 = 1
_OPP2 = 2
_EMPTY = 0


class SimpleHeuristicsDoublesPlayer(BaseHeuristic2v2):
    """Lightweight stat-aware doubles baseline."""

    def _score_order(
        self, order: SingleBattleOrder, pokemon, slot: int, battle
    ) -> float:
        action = order.order

        # We do not implement proactive switching here; keep it purely offensive.
        if not isinstance(action, Move):
            return -1.0
        if action.base_power <= 1:
            return 0.0

        target = order.move_target
        if target < 0:
            # Ally-targeting or self-hits are not rewarded in this simple baseline.
            return 0.0

        my_status = get_status_name(pokemon)
        opps = battle.opponent_active_pokemon or []

        if target == _EMPTY:
            living = [o for o in opps if o is not None]
            return max(
                (calculate_base_damage(action, pokemon, o, my_status) for o in living),
                default=0.0,
            )

        idx = target - 1
        if idx < 0 or idx >= len(opps) or opps[idx] is None:
            return 0.0
        return calculate_base_damage(action, pokemon, opps[idx], my_status)

