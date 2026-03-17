"""Heuristic V4 Doubles: Tactical Synergy and Focus Fire.

The 'Master' heuristic for doubles. Unlike previous versions that scored 
slots independently, V7 evaluates pairs of actions to reward synergy:
1. Focus Fire: Bonus for coordinating both active Pokémon to KO a high threat.
2. Protect Strategy: Encourages protecting a vulnerable teammate while the other attacks.
3. KO Priority: Heavily weights moves that guaranteed a knock-out.
"""

from __future__ import annotations

import logging

from poke_env.player.battle_order import DoubleBattleOrder
from poke_env.battle.move import Move

from .v3 import HeuristicV3Doubles
from ..core.common import calculate_base_damage, get_status_name

logger = logging.getLogger(__name__)

_OPP1 = 1
_OPP2 = 2

class HeuristicV4Doubles(HeuristicV3Doubles):
    """Pairwise Synergy Heuristic."""

    @property
    def tracks_moves(self) -> bool:
        return True

    def choose_doubles_move(self, battle) -> DoubleBattleOrder:
        """Override base orchestration to allow cross-slot synergy scoring."""
        try:
            slot0_valid, slot1_valid = battle.valid_orders
            active = battle.active_pokemon
            mon0 = active[0] if len(active) > 0 else None
            mon1 = active[1] if len(active) > 1 else None

            valid_pairs = DoubleBattleOrder.join_orders(slot0_valid, slot1_valid)
            if not valid_pairs:
                return self.choose_random_doubles_move(battle)

            best_pair = None
            best_score = -float('inf')

            for pair in valid_pairs:
                score = self._score_pair(pair, mon0, mon1, battle)
                if score > best_score:
                    best_score = score
                    best_pair = pair

            return best_pair or self.choose_random_doubles_move(battle)
        except Exception as e:
            logger.error(f"Error in V4 decision: {e}")
            return self.choose_random_doubles_move(battle)

    def _score_pair(self, pair: DoubleBattleOrder, mon0, mon1, battle) -> float:
        """Score a combination of two actions."""
        o0 = pair.first_order
        o1 = pair.second_order

        # Base scores from V3 logic (damage, priority, weather, terrain, etc.)
        s0 = self._score_order(o0, mon0, 0, battle) if mon0 else 0.0
        s1 = self._score_order(o1, mon1, 1, battle) if mon1 else 0.0
        
        total = s0 + s1

        # Synergy Adjustments
        total += self._synergy_focus_fire(o0, o1, mon0, mon1, battle)
        total += self._synergy_protect(o0, o1, mon0, mon1, battle)
        total += self._synergy_ko_bonus(o0, mon0, battle)
        total += self._synergy_ko_bonus(o1, mon1, battle)

        return total

    def _synergy_focus_fire(self, o0, o1, mon0, mon1, battle) -> float:
        """Reward attacking the same specific opponent."""
        if not (isinstance(o0.order, Move) and isinstance(o1.order, Move)):
            return 0.0
        
        if o0.move_target == o1.move_target and o0.move_target in [_OPP1, _OPP2]:
            idx = o0.move_target - 1
            opps = battle.opponent_active_pokemon
            if idx < len(opps) and opps[idx]:
                hp_pct = opps[idx].current_hp_fraction
                return 30.0 * (1.1 - hp_pct)  # Higher bonus for lower HP targets
        
        return 0.0

    def _synergy_protect(self, o0, o1, mon0, mon1, battle) -> float:
        """Reward protecting a teammate that is attacking or low HP."""
        bonus = 0.0
        orders = [o0, o1]
        mons = [mon0, mon1]
        
        is_p = [self._is_protect(o.order) if isinstance(o.order, Move) else False for o in orders]
        
        if is_p[0] and is_p[1]:
            return -20.0  # Penalize double protect

        for i in range(2):
            if is_p[i] and mons[i]:
                if mons[i].current_hp_fraction < 0.4:
                    bonus += 25.0
                other_idx = 1 - i
                if isinstance(orders[other_idx].order, Move) and not is_p[other_idx]:
                    bonus += 10.0
                    
        return bonus

    def _synergy_ko_bonus(self, order, pokemon, battle) -> float:
        """Extra points if this move is likely to KO an opponent."""
        if not (isinstance(order.order, Move) and pokemon):
            return 0.0
        
        move = order.order
        target_idx = order.move_target - 1
        opps = battle.opponent_active_pokemon
        
        if target_idx < 0 or target_idx >= len(opps) or not opps[target_idx]:
            return 0.0
            
        target = opps[target_idx]
        dmg = calculate_base_damage(move, pokemon, target, get_status_name(pokemon))
        
        # current_hp is absolute HP or fraction depending on poke-env version/setup
        # Assuming current_hp_fraction for robustness
        estimated_dmg_pct = dmg / (target.max_hp or 100) # Simple estimate
        if estimated_dmg_pct >= target.current_hp_fraction:
            return 60.0  # Finish them!
            
        return 0.0

    def _is_protect(self, move: Move) -> bool:
        """Is this a protection move?"""
        return move.id in ["protect", "detect", "banefulbunker", "spikyshield", "kingsshield", "obstruct"]

    def _score_order(self, order, pokemon, slot, battle) -> float:
        score = super()._score_order(order, pokemon, slot, battle)
        
        if isinstance(order.order, Move) and self.tracks_moves:
            used = self.get_used_moves(battle.battle_tag)
            if order.order.id in used:
                score *= 0.85 # Penalty for repetitiveness
                
        return score
