"""Heuristic V5: Boost-Aware Field Expert with Smart Switching.

Extends V4's field awareness with stat-boost-aware damage estimation:

- **Stat-Boost Awareness**: Calculates damage using stage-multiplied atk/def.
- **Weather & Terrain**: Same field modifiers as V4.
- **Smart Switching**: V3's proven triggers with best-type-matchup target selection.
- **Relaxed Switch Threshold**: Accepts switch-ins up to 2.0× (not just <=1.0).
"""

from __future__ import annotations

from ...core.base import BaseHeuristic1v1
from ...core.common import get_speed, get_status_name


class HeuristicV5(BaseHeuristic1v1):
    """Stat-boost-aware heuristic with field effects and smart switching."""

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

        # 1. Score all moves with boost-aware damage + field modifiers
        best_move = None
        max_score = -1.0
        max_raw_damage = -1.0

        for move in battle.available_moves or []:
            dmg = self._estimate_damage(move, me, opp, battle)

            if dmg > max_raw_damage:
                max_raw_damage = dmg

            score = self._score_move(move, dmg)

            if score > max_score:
                max_score, best_move = score, move

        # 2. V3's proven switching triggers + smart target selection
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

    # -- Boost-aware damage estimation ------------------------------------

    @staticmethod
    def _get_boosted_stat(pokemon, stat_name: str) -> float:
        """Calculate a stat with in-battle stage boosts applied."""
        raw_stat = pokemon.stats.get(stat_name) or pokemon.base_stats.get(stat_name, 100)
        boost = pokemon.boosts.get(stat_name, 0)

        if boost > 0:
            multiplier = (2.0 + boost) / 2.0
        elif boost < 0:
            multiplier = 2.0 / (2.0 - boost)
        else:
            multiplier = 1.0

        return raw_stat * multiplier

    def _estimate_damage(self, move, attacker, defender, battle) -> float:
        """Estimate move damage with stat boosts, weather, and terrain."""
        if move.base_power <= 1:
            return 0.0

        if move.category.name == "PHYSICAL":
            atk = self._get_boosted_stat(attacker, "atk")
            defe = self._get_boosted_stat(defender, "def")
            if get_status_name(attacker) == "BRN":
                atk *= 0.5
        else:
            atk = self._get_boosted_stat(attacker, "spa")
            defe = self._get_boosted_stat(defender, "spd")

        defe = max(defe, 1.0)

        effectiveness = defender.damage_multiplier(move)
        stab = 1.5 if move.type in attacker.types else 1.0

        damage = (atk / defe) * move.base_power * stab * effectiveness

        damage = self._apply_weather(damage, move, battle)
        damage = self._apply_terrain(damage, move, battle)

        return float(damage)

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

    def _score_move(self, move, dmg: float) -> float:
        """Score a move: ``damage × accuracy``, with priority boost."""
        accuracy = move.accuracy if isinstance(move.accuracy, float) else 1.0
        score = dmg * accuracy

        if move.entry.get("priority", 0) > 0:
            score *= 1.2

        return float(score)

    # -- Smart switching ---------------------------------------------------

    @staticmethod
    def _get_best_switch(battle):
        """Pick the teammate with the best defensive typing vs the opponent."""
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
