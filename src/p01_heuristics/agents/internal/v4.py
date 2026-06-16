"""Heuristic V4: Field-Aware Damage Strategist with Smart Switching.

Extends the V3 defensive foundation with:

- **Smart Switch Targets**: Picks the best defensive typing teammate (not slot 0).
- **Field Effects**: Integrates weather (sun/rain) and terrain
  (electric/grassy/psychic) modifiers into the damage estimate.
- **Accuracy-Weighted Scoring**: Selects moves by ``damage × accuracy``.
- **Priority Boost**: Gives a 1.5× scoring bonus to priority moves.
- **Conservative Pivoting**: Uses V3's proven TOX/outsped switching triggers,
  but routes to the best available switch-in.
"""

from __future__ import annotations

from p00_core.core.base import BaseHeuristic1v1
from p00_core.core.common import calculate_base_damage, get_speed, get_status_name


class HeuristicV4(BaseHeuristic1v1):
    """Field-aware heuristic with smart switch selection."""

    @property
    def tracks_moves(self) -> bool:
        return True

    def _select_action(self, battle):
        me = battle.active_pokemon
        opp = battle.opponent_active_pokemon

        if me is None or opp is None:
            return None

        my_status = get_status_name(me)
        opp_status = get_status_name(opp)
        my_speed = get_speed(me, my_status)
        opp_speed = get_speed(opp, opp_status)

        # 1. Score all moves with field modifiers
        best_move = None
        max_score = -1.0
        max_raw_damage = -1.0

        for move in battle.available_moves or []:
            dmg = calculate_base_damage(move, me, opp, my_status)

            if dmg > max_raw_damage:
                max_raw_damage = dmg

            score = dmg
            score = self._apply_weather(score, move, battle)
            score = self._apply_terrain(score, move, battle)

            accuracy = move.accuracy if isinstance(move.accuracy, float) else 1.0
            score *= accuracy

            if move.entry.get("priority", 0) > 0:
                score *= 1.5

            if score > max_score:
                max_score, best_move = score, move

        # 2. V3's proven switching triggers, but with smart target selection
        if battle.available_switches:
            if my_status == "TOX" and me.status_counter > 2:
                switch = self._get_best_switch(battle)
                if switch:
                    return self.create_order(switch)
                return self.create_order(battle.available_switches[0])

            if max_raw_damage < 20 and my_speed < opp_speed:
                switch = self._get_best_switch(battle)
                if switch:
                    return self.create_order(switch)
                return self.create_order(battle.available_switches[0])

        # 3. Execute best move
        if best_move:
            self._record_used_move(battle.battle_tag, best_move.id)
            return self.create_order(best_move)

        return None

    # -- Field modifiers ---------------------------------------------------

    @staticmethod
    def _apply_weather(damage: float, move, battle) -> float:
        if not battle.weather:
            return damage
        w_name = str(battle.weather).upper()
        move_type = move.type.name
        if "SUN" in w_name:
            if move_type == "FIRE":
                damage *= 1.5
            elif move_type == "WATER":
                damage *= 0.5
        elif "RAIN" in w_name:
            if move_type == "WATER":
                damage *= 1.5
            elif move_type == "FIRE":
                damage *= 0.5
        return damage

    @staticmethod
    def _apply_terrain(damage: float, move, battle) -> float:
        if not battle.fields:
            return damage
        move_type = move.type.name
        terrain_boosts = {
            "ELECTRIC": "ELECTRIC",
            "GRASSY": "GRASS",
            "PSYCHIC": "PSYCHIC",
        }
        for field in battle.fields:
            f_name = str(field).upper()
            for terrain_key, boosted_type in terrain_boosts.items():
                if terrain_key in f_name and move_type == boosted_type:
                    damage *= 1.3
        return damage

    # -- Smart switching ---------------------------------------------------

    @staticmethod
    def _get_best_switch(battle):
        """Pick the teammate with the best defensive typing vs the opponent.

        Returns the switch-in whose worst type weakness against the opponent is
        lowest, accepting any teammate that is at most neutral (<=2.0) to the
        opponent's STAB types.
        """
        opp = battle.opponent_active_pokemon
        if opp is None:
            return None

        best_teammate = None
        min_multiplier = 4.0

        for pokemon in battle.available_switches:
            valid_types = [t for t in opp.types if t is not None]
            if not valid_types:
                worst = 1.0
            else:
                worst = max(pokemon.damage_multiplier(t) for t in valid_types)

            if worst < min_multiplier:
                min_multiplier = worst
                best_teammate = pokemon

        return best_teammate if min_multiplier <= 2.0 else None
