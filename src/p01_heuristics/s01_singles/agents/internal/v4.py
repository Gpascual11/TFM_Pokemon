"""Heuristic V4: Expert-Level Singles Strategy.

This heuristic represents the most advanced version, employing a sophisticated decision pipeline:

- **Immediate KO Check**: Prioritizes moves that guarantee a knockout,
  scanning available moves sorted by priority.
- **Defensive Pivoting**: Initiates a switch if the active Pokémon is in
  immediate danger or severely poisoned.
- **Scored Offensive**: Selects the optimal offensive move based on a
  ``damage × accuracy`` score, with an additional boost for priority moves.

The damage estimation incorporates environmental factors such as weather
(sun/rain) and terrain (electric/grassy/psychic) modifiers, extending the
standard physical/special damage formula.
"""

from __future__ import annotations

from ...core.base import BaseHeuristic1v1
from ...core.common import get_status_name
import logging

logger = logging.getLogger(__name__)


class HeuristicV4(BaseHeuristic1v1):
    """Expert-level singles heuristic incorporating KO detection, defensive pivoting, and field effects."""

    @property
    def tracks_moves(self) -> bool:
        """Indicates that this heuristic tracks move usage."""
        return True

    def _select_action(self, battle):
        """
        Selects the optimal action (move or switch) based on the heuristic's decision pipeline.

        Prioritizes defensive pivoting if the active Pokémon is in danger or badly poisoned.
        Otherwise, selects the move with the highest calculated score.
        """
        me = battle.active_pokemon
        opp = battle.opponent_active_pokemon

        if me is None or opp is None:
            return None

        my_status = get_status_name(me)

        if self._is_in_danger(me, opp) or (my_status == "TOX" and me.status_counter > 2):
            switch = self._get_best_switch(battle)
            if switch:
                return self.create_order(switch)

        best_move = None
        max_score = -1.0
        for move in battle.available_moves or []:
            score = self._score_move(move, me, opp, battle)
            if score > max_score:
                max_score, best_move = score, move

        if best_move:
            self._record_used_move(battle.battle_tag, best_move.id)
            return self.create_order(best_move)

        return None

    # -- Damage estimation ------------------------------------------------

    def _estimate_damage(self, move, attacker, defender, battle) -> float:
        """Estimate move damage including weather and terrain modifiers."""
        if move.base_power <= 1:
            return 0.0

        if move.category.name == "PHYSICAL":
            atk = attacker.stats.get("atk") or attacker.base_stats["atk"]
            defe = defender.stats.get("def") or defender.base_stats["def"]
            if attacker.status and attacker.status.name == "BRN":
                atk *= 0.5
        else:
            atk = attacker.stats.get("spa") or attacker.base_stats["spa"]
            defe = defender.stats.get("spd") or defender.base_stats["spd"]

        multiplier = defender.damage_multiplier(move)
        stab = 1.5 if move.type in attacker.types else 1.0
        damage = ((0.5 * move.base_power * (atk / defe) * stab) + 2) * multiplier

        damage = self._apply_weather(damage, move, battle)
        damage = self._apply_terrain(damage, move, battle)

        return float(damage)

    @staticmethod
    def _apply_weather(damage: float, move, battle) -> float:
        """Apply sun/rain damage modifiers."""
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
        """Apply terrain-based damage boosts (1.3× for matching types)."""
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

    def _score_move(self, move, attacker, defender, battle) -> float:
        """Score a move: ``damage × accuracy``, boosted 1.5× for priority."""
        dmg = self._estimate_damage(move, attacker, defender, battle)
        accuracy = move.accuracy if isinstance(move.accuracy, float) else 1.0
        score = dmg * accuracy
        if move.entry.get("priority", 0) > 0:
            score *= 1.5
        return float(score)

    # -- Defensive helpers ------------------------------------------------

    @staticmethod
    def _is_in_danger(me, opp) -> bool:
        """True when outsped by an opponent with super-effective STAB, or HP < 30%."""
        if me is None or opp is None:
            return False

        opp_speed = opp.stats.get("spe") or opp.base_stats["spe"]
        my_speed = me.stats.get("spe") or me.base_stats["spe"]

        if my_speed <= opp_speed:
            for opp_type in opp.types:
                if opp_type is not None and me.damage_multiplier(opp_type) >= 2.0:
                    return True

        return me.current_hp_fraction < 0.30

    @staticmethod
    def _get_best_switch(battle):
        """Pick the teammate with the best defensive typing vs the opponent.

        Returns the safest switch-in whose worst type weakness is ≤ 1.0×,
        or ``None`` if no safe switch exists.
        """
        opp = battle.opponent_active_pokemon
        if opp is None:
            return None

        best_teammate = None
        min_multiplier = 4.0

        for pokemon in battle.available_switches:
            # Safety check: ensure opp.types is not empty before calling max()
            valid_types = [t for t in opp.types if t is not None]
            if not valid_types:
                worst = 1.0
            else:
                worst = max(pokemon.damage_multiplier(t) for t in valid_types)
                
            if worst < min_multiplier:
                min_multiplier = worst
                best_teammate = pokemon

        return best_teammate if min_multiplier <= 1.0 else None
