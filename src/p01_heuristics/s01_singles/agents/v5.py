from __future__ import annotations

from poke_env.data import GenData

from ..core.base import BaseHeuristic1v1
from ..core.common import get_status_name
import logging

logger = logging.getLogger(__name__)


class HeuristicV5(BaseHeuristic1v1):
    """V5 Heuristic: Accurate damage estimation + smart switching + KO priority.

    Improvements over V3:
    - Stat-boost awareness (attack/defence stage multipliers)
    - Weather and terrain damage modifiers
    - KO pre-check (priority-sorted to grab quick KOs with fast or priority moves)
    - Danger-aware switching: considers HP fraction, toxic counter, and matchup
    - Best-switch selection with relaxed threshold (takes neutral or better)
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.dm = GenData.from_gen(9)

    @property
    def tracks_moves(self) -> bool:
        return True

    # -- Template hooks ---------------------------------------------------

    def _pre_move_hook(self, battle):
        """Short-circuit with a guaranteed KO move (priority-first)."""
        me = battle.active_pokemon
        opp = battle.opponent_active_pokemon

        if not battle.available_moves or me is None or opp is None:
            return None

        sorted_moves = sorted(
            battle.available_moves,
            key=lambda m: m.entry.get("priority", 0),
            reverse=True,
        )
        for move in sorted_moves:
            if self._estimate_damage(move, me, opp, battle) >= opp.current_hp:
                self._record_used_move(battle.battle_tag, move.id)
                return self.create_order(move)

        return None

    def _select_action(self, battle):
        me = battle.active_pokemon
        opp = battle.opponent_active_pokemon

        if me is None or opp is None:
            return None

        # 1. Evaluate all moves to find the best and its raw damage
        best_move = None
        max_score = -1.0
        max_raw_damage = 0.0

        for move in battle.available_moves or []:
            dmg = self._estimate_damage(move, me, opp, battle)
            score = self._score_move(move, dmg)

            if score > max_score:
                max_score, best_move = score, move
            if dmg > max_raw_damage:
                max_raw_damage = dmg

        # 2. Smart switching: only when truly necessary
        if battle.available_switches and self._needs_to_switch(me, opp, max_raw_damage):
            switch = self._get_best_switch(battle)
            if switch:
                return self.create_order(switch)

        # 3. Execute the best evaluated move
        if best_move:
            self._record_used_move(battle.battle_tag, best_move.id)
            return self.create_order(best_move)

        return None

    # -- Damage & Stat estimation -----------------------------------------

    def _get_boosted_stat(self, pokemon, stat_name: str) -> float:
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
        """Estimate move damage.

        Uses the same base formula as V3 (``atk/defe * bp * stab * eff``) so
        that the switching threshold and KO check are on the same numeric scale,
        then layers in stat-boost, weather, and terrain modifiers.
        """
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

        # V3-compatible base formula (no scaling constant that skews the scale)
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
        """Score a move: ``damage × accuracy``, with a small boost for priority moves.

        Uses float-only accuracy check (mirrors V4) to avoid the boolean trap
        where ``True`` evaluates as 1 and ``True / 100.0 == 0.01``.
        """
        # poke-env reports accuracy as a float (0.0–1.0) or True for guaranteed
        accuracy = move.accuracy if isinstance(move.accuracy, float) else 1.0

        score = dmg * accuracy

        # Modest priority bias: prefer priority moves when they land KOs (handled
        # in _pre_move_hook), but don't blindly prefer weak +1 priority moves
        if move.entry.get("priority", 0) > 0:
            score *= 1.2

        return float(score)

    # -- Defensive helpers ------------------------------------------------

    def _needs_to_switch(self, me, opp, max_damage: float) -> bool:
        """Decide whether switching out is the right call.

        Triggers on three independent conditions (mirrors V3's logic plus
        HP-fraction danger check from V4):
        1. Badly poisoned for more than 2 turns → escape toxic stacking.
        2. Outsped AND can't deal meaningful damage → pivot rather than take
           a hit and do nothing.
        3. Critically low HP (<25%) → don't sacrifice if a better switch exists.
        """
        my_status = get_status_name(me)
        my_speed = self._get_boosted_stat(me, "spe")
        opp_speed = self._get_boosted_stat(opp, "spe")

        if my_status == "TOX" and me.status_counter > 2:
            return True

        if max_damage < 20 and my_speed < opp_speed:
            return True

        if me.current_hp_fraction < 0.25:
            return True

        return False

    @staticmethod
    def _get_best_switch(battle):
        """Pick the teammate with the best defensive typing vs the opponent.

        Returns the switch-in whose worst type weakness is lowest, as long as
        it is ≤ 2.0× (i.e. not doubly weak to every opponent type).  The
        relaxed threshold (was 1.0) means V5 will nearly always find a smart
        switch rather than falling back to a blind slot-0 pick.
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

        # Accept any switch that isn't doubly weak to every opponent type
        return best_teammate if min_multiplier <= 2.0 else None
