from __future__ import annotations

from ...core.common import calculate_base_damage, get_speed, get_status_name
from .v3 import HeuristicV3


class HeuristicV6(HeuristicV3):
    """Advanced Singles Strategy with Field Awareness & Expert Modifiers.
    
    Heuristic V6 represents the pinnacle of the rule-based approach, 
    combining the stable defensive foundation of V3 with expert field-state 
    knowledge.
    
    Logic & Expert Enhancements:
    - Dynamic Damage Calculation: Adjusts move power based on active Weather (Sun/Rain) and Terrain (Electric/Grassy/Psychic).
    - Priority Valuation: Applies strategic weighting to priority moves to secure KOs or apply pressure.
    - Stable Pivoting: Retains the proven defensive toxicity-escape and outsped-pivot logic from V3.
    """

    def _select_action(self, battle):
        me = battle.active_pokemon
        opp = battle.opponent_active_pokemon

        if me is None or opp is None:
            return None

        my_status = get_status_name(me)
        opp_status = get_status_name(opp)
        my_speed = get_speed(me, my_status)
        opp_speed = get_speed(opp, opp_status)

        best_move = None
        max_score = -1.0
        max_raw_damage = -1.0  # Tracked for V3 switch logic threshold

        if battle.available_moves:
            for move in battle.available_moves:
                # 1. Calculate baseline damage using the common helper
                dmg = calculate_base_damage(move, me, opp, my_status)

                # Update raw damage for switching threshold
                if dmg > max_raw_damage:
                    max_raw_damage = dmg

                # 2. Apply Expert Modifiers for Move Selection (The V4/V5 Magic)
                score = dmg

                # Apply Weather
                if battle.weather:
                    w_name = str(battle.weather).upper()
                    if "SUN" in w_name:
                        if move.type.name == "FIRE":
                            score *= 1.5
                        elif move.type.name == "WATER":
                            score *= 0.5
                    elif "RAIN" in w_name:
                        if move.type.name == "WATER":
                            score *= 1.5
                        elif move.type.name == "FIRE":
                            score *= 0.5

                # Apply Terrain
                if battle.fields:
                    t_boosts = {
                        "ELECTRIC": "ELECTRIC",
                        "GRASSY": "GRASS",
                        "PSYCHIC": "PSYCHIC",
                    }
                    for field in battle.fields:
                        f_name = str(field).upper()
                        for t_key, t_type in t_boosts.items():
                            if t_key in f_name and move.type.name == t_type:
                                score *= 1.3

                # Apply Priority Boost (Conservative 1.2x)
                if move.entry.get("priority", 0) > 0:
                    score *= 1.2

                # Select the best move based on the MODIFIED score
                if score > max_score:
                    max_score, best_move = score, move

        # 3. Use V3's EXACT switching logic. No custom panic-switching.
        if battle.available_switches:
            if my_status == "TOX" and me.status_counter > 2:
                return self.create_order(battle.available_switches[0])
            if max_raw_damage < 20 and my_speed < opp_speed:
                return self.create_order(battle.available_switches[0])

        if best_move:
            self._record_used_move(battle.battle_tag, best_move.id)
            return self.create_order(best_move)

        return None
