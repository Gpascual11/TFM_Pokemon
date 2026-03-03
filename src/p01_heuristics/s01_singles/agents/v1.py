"""Heuristic V1 — simple max-damage selector.

Picks the move with the highest ``base_power × effectiveness × STAB``.
No switching logic.  This is the simplest possible singles heuristic
and serves as the performance baseline.
"""

from __future__ import annotations

from ..core.base import BaseHeuristic1v1


class HeuristicV1(BaseHeuristic1v1):
    """Always select the move with the highest raw damage estimate."""

    def _select_action(self, battle):
        if not battle.available_moves:
            return None

        best_move = max(
            battle.available_moves,
            key=lambda m: self._score(m, battle),
        )
        return self.create_order(best_move)

    @staticmethod
    def _score(move, battle) -> float:
        """Damage proxy: ``base_power × effectiveness × STAB``."""
        if move.base_power <= 1:
            return 0.0
        target = battle.opponent_active_pokemon
        if target is None:
            return 0.0
        effectiveness = target.damage_multiplier(move)
        stab = 1.5 if move.type in battle.active_pokemon.types else 1.0
        return float(move.base_power * effectiveness * stab)
