"""Max Base Power Baseline for Doubles.

A simple heuristic that consistently selects the move with the highest 
base power. Adapted from poke-env to use safe 2v2 orders.
"""

from __future__ import annotations

from poke_env.player import Player, DoubleBattleOrder, DefaultBattleOrder
from poke_env.player.battle_order import SingleBattleOrder
from poke_env.environment.move import Move
from poke_env.environment.pokemon import Pokemon

class MaxPowerDoublesPlayer(Player):
    def choose_move(self, battle):
        if not battle.active_pokemon:
            return self.choose_random_move(battle)

        slot0_orders, slot1_orders = battle.valid_orders

        def get_order_bp(order: SingleBattleOrder) -> float:
            if not order.order or not hasattr(order.order, "base_power"):
                return -1.0
            bp = getattr(order.order, "base_power", 0)
            target = order.move_target
            # simple target logic: penalize friendly attacks
            if target is not None and target < 0:
                return -1.0
            return bp

        best0 = max(slot0_orders, key=get_order_bp, default=None)
        best1 = max(slot1_orders, key=get_order_bp, default=None)

        # Fallbacks to default action if no moves (or only switches)
        if not best0:
            best0 = DefaultBattleOrder()
        if not best1:
            best1 = DefaultBattleOrder()

        # Safely resolve duplicates (e.g., both switching to same mon)
        valid_pairs = DoubleBattleOrder.join_orders(
            [best0] if not isinstance(best0, list) else slot0_orders,
            [best1] if not isinstance(best1, list) else slot1_orders,
        )

        if valid_pairs:
            return max(
                valid_pairs,
                key=lambda p: get_order_bp(p.first_order) + get_order_bp(p.second_order),
            )
        
        return self.choose_random_doubles_move(battle)
