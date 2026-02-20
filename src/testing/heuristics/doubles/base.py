"""Abstract base class for 2-vs-2 heuristic strategies.

We use a **score-then-combine** pattern:

1. `battle.valid_orders` gives two lists of pre-validated `SingleBattleOrder`
   objects (one per active slot) with correct targets already set by poke-env.
2. Subclasses implement `_score_order` to rank each candidate.
3. `DoubleBattleOrder.join_orders` produces all valid (slot-0, slot-1) pairings.
4. We pick the pair with the highest combined score.
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
        super().__init__(*args, **kwargs)
        self._used_moves_by_battle: Dict[str, Set[str]] = {}

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
                return self._score_order(o, mon0, 0, battle) if mon0 is not None else 0.0

            def score1(o: SingleBattleOrder) -> float:
                return self._score_order(o, mon1, 1, battle) if mon1 is not None else 0.0

            valid_pairs = DoubleBattleOrder.join_orders(slot0_orders, slot1_orders)
            if not valid_pairs:
                return self.choose_random_doubles_move(battle)

            return max(valid_pairs, key=lambda p: score0(p.first_order) + score1(p.second_order))
        except Exception:
            return self.choose_random_doubles_move(battle)

    @abc.abstractmethod
    def _score_order(self, order: SingleBattleOrder, pokemon, slot: int, battle) -> float:
        """Score a single-slot order. Higher = more preferred.

        :param order: A pre-validated order from ``battle.valid_orders``.
        :param pokemon: Active Pokémon for this slot (may be ``None``).
        :param slot: Slot index (0 or 1).
        :param battle: Current ``DoubleBattle`` state.
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

    def _best_damage_against_opponents(self, move, attacker, opponents, attacker_status: str) -> float:
        """Max damage estimate across all living opponents for *move*."""
        from .common import calculate_base_damage
        return max(
            (calculate_base_damage(move, attacker, opp, attacker_status)
             for opp in opponents if opp is not None),
            default=0.0,
        )
