"""Abstract base class for 2-vs-2 heuristic strategies.

Implements a **score-then-combine** decision pattern:
1. Validates possible orders for each active Pokémon slot.
2. Subclasses implement `_score_order` to evaluate individual slot actions.
3. Combines slot scores to select the optimal pair of actions (move or switch).
"""

from __future__ import annotations

import abc
from typing import Dict, Set

from poke_env.player import Player
from poke_env.player.battle_order import (
    DoubleBattleOrder,
    DefaultBattleOrder,
    SingleBattleOrder,
)


class BaseHeuristic2v2(Player, abc.ABC):
    """Base for all doubles heuristic players.

    Subclasses only need to implement :meth:`_score_order`.
    """

    def __init__(self, *args, **kwargs) -> None:
        """Initialize the doubles heuristic player.

        Tracks move usage across battles if enabled by the subclass.
        """
        super().__init__(*args, **kwargs)
        self._used_moves_by_battle: Dict[str, Set[str]] = {}

    def reset_battles(self) -> None:
        """Clear both the poke-env battle history and our custom move tracking."""
        super().reset_battles()
        self._used_moves_by_battle.clear()

    # ------------------------------------------------------------------
    # poke-env entry point
    # ------------------------------------------------------------------

    def choose_move(self, battle):
        """Called by poke-env each turn. Dispatches doubles battles here."""
        from poke_env.battle.double_battle import DoubleBattle

        if isinstance(battle, DoubleBattle):
            return self.choose_doubles_move(battle)
        return self.choose_random_move(battle)

    # ------------------------------------------------------------------
    # Doubles orchestration
    # ------------------------------------------------------------------

    def choose_doubles_move(self, battle) -> DoubleBattleOrder:
        """Return the highest-scoring valid doubles order.

        Uses `battle.valid_orders` for correct pre-computed targets,
        `join_orders` to filter illegal combos (e.g. duplicate switches),
        and selects by `max(score_slot0 + score_slot1)`.
        Falls back to `choose_random_doubles_move` on any error.
        """
        try:
            slot0_orders, slot1_orders = battle.valid_orders
            active = battle.active_pokemon
            mon0 = active[0] if len(active) > 0 else None
            mon1 = active[1] if len(active) > 1 else None

            def score0(o: SingleBattleOrder) -> float:
                return (
                    self._score_order(o, mon0, 0, battle) if mon0 is not None else 0.0
                )

            def score1(o: SingleBattleOrder) -> float:
                return (
                    self._score_order(o, mon1, 1, battle) if mon1 is not None else 0.0
                )

            valid_pairs = DoubleBattleOrder.join_orders(slot0_orders, slot1_orders)
            if not valid_pairs:
                return self.choose_random_doubles_move(battle)

            return max(
                valid_pairs,
                key=lambda p: score0(p.first_order) + score1(p.second_order),
            )
        except Exception:
            return self.choose_random_doubles_move(battle)

    @abc.abstractmethod
    def _score_order(
        self, order: SingleBattleOrder, pokemon, slot: int, battle
    ) -> float:
        """Calculate a preference score for a single action in a specific slot.

        This method must be implemented by subclasses to define the primary
        decision logic. The scores from both active slots are summed to
        determine the final 'join_order' choice.

        :param order: A pre-validated order (move or switch).
        :param pokemon: The active Pokémon in the target slot.
        :param slot: Index of the active slot (0 or 1).
        :param battle: The current DoubleBattle state.
        :return: A numerical score; higher values indicate better actions.
        """

    # ------------------------------------------------------------------
    # Move tracking helpers
    # ------------------------------------------------------------------

    @property
    def tracks_moves(self) -> bool:
        """``True`` if this heuristic records move usage per battle."""
        return False

    def _record_used_move(self, battle_tag: str, move_id: str) -> None:
        """Record that *move_id* was used in *battle_tag*."""
        self._used_moves_by_battle.setdefault(battle_tag, set()).add(move_id)

    def get_used_moves(self, battle_tag: str) -> Set[str]:
        """Return the set of move IDs used in *battle_tag*."""
        return self._used_moves_by_battle.get(battle_tag, set())

    # ------------------------------------------------------------------
    # Shared scoring helper
    # ------------------------------------------------------------------

    def _best_damage_against_opponents(
        self, move, attacker, opponents, attacker_status: str
    ) -> float:
        """Max damage estimate across all living opponents for *move*."""
        from .common import calculate_base_damage

        return max(
            (
                calculate_base_damage(move, attacker, opp, attacker_status)
                for opp in opponents
                if opp is not None
            ),
            default=0.0,
        )
