"""Simple Heuristics Baseline for Doubles.

A wrapper around poke-env's SimpleHeuristicsPlayer that safely uses 
DefaultBattleOrder instead of the deprecated PassBattleOrder for Doubles.
"""

from __future__ import annotations

import random
from typing import List

from poke_env.player import DoubleBattleOrder, DefaultBattleOrder
from poke_env.player.baselines import SimpleHeuristicsPlayer
from poke_env.environment.double_battle import DoubleBattle
from poke_env.environment.move import Move
from poke_env.player.battle_order import SingleBattleOrder

class PseudoBattle:
    """Mock battle to pass to singles heuristic."""
    def __init__(self, battle, active_id, opp_id):
        self._battle = battle
        self.active_id = active_id
        self.opp_id = opp_id

    @property
    def active_pokemon(self):
        return self._battle.active_pokemon[self.active_id]

    @property
    def opponent_active_pokemon(self):
        return self._battle.opponent_active_pokemon[self.opp_id]
        
    @property
    def available_moves(self):
        return self._battle.available_moves[self.active_id]
        
    @property
    def available_switches(self):
        return self._battle.available_switches[self.active_id]
        
    @property
    def team(self):
        return self._battle.team
        
    @property
    def opponent_team(self):
        return self._battle.opponent_team
        
    @property
    def opponent_side_conditions(self):
        return self._battle.opponent_side_conditions
        
    @property
    def side_conditions(self):
        return self._battle.side_conditions
        
    def __getattr__(self, name):
        return getattr(self._battle, name)


class SimpleHeuristicsDoublesPlayer(SimpleHeuristicsPlayer):
    """Wrapper that fixes poke-env's DoubleBattleOrder generation."""

    def choose_move(self, battle):
        if not isinstance(battle, DoubleBattle):
            return self.choose_singles_move(battle)[0]

        orders = []
        for active_id in [0, 1]:
            if (
                battle.active_pokemon[active_id] is None
                and not battle.available_switches[active_id]
            ):
                orders.append(DefaultBattleOrder())
                continue

            results = [
                self.choose_singles_move(PseudoBattle(battle, active_id, opp_id))
                for opp_id in [0, 1]
            ]
            possible_orders = [r[0] for r in results]
            scores = [r[1] for r in results]
            
            for order in possible_orders:
                mon = battle.active_pokemon[active_id]
                if (
                    order is not None
                    and hasattr(order, "order")
                    and isinstance(order.order, Move)
                    and mon is not None
                ):
                    target_idx = [o for o in possible_orders].index(order) + 1
                    possible_targets = battle.get_possible_showdown_targets(
                        order.order, mon
                    )
                    if target_idx not in possible_targets:
                        target_idx = possible_targets[0] if possible_targets else 0
                    order.move_target = target_idx
                    
            scores = [
                scores[i]
                * self.get_double_target_multiplier(battle, possible_orders[i])
                for i in [0, 1]
            ]
            
            best_idx = 0 if scores[0] >= scores[1] else 1
            best_order = results[best_idx][0]
            
            is_force_switch = battle.force_switch == [[False, True], [True, False]][active_id]
            is_forced_trapped = (
                len(battle.available_switches[active_id]) == 1
                and battle.force_switch == [True, True]
                and active_id == 1
            )
            
            if is_force_switch or is_forced_trapped:
                orders.append(DefaultBattleOrder())
            else:
                orders.append(best_order)

        # Resolve
        if hasattr(orders[0], "order") and hasattr(orders[1], "order"):
            joined_orders = DoubleBattleOrder.join_orders([orders[0]], [orders[1]])
            if joined_orders:
                return joined_orders[0]
                
        return DoubleBattleOrder(orders[0] or DefaultBattleOrder(), orders[1] or DefaultBattleOrder())
