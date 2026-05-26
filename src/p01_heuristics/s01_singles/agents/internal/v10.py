"""Heuristic V10: Anti-Abyssal Specialist.

V8's proven boost-aware core + three features Abyssal cannot match:

1. **Status Moves**: Toxic on bulky walls we can't break, Will-O-Wisp on
   physical attackers, Thunder Wave on faster threats. Only fires when our
   best attack scores below threshold AND opponent has no status.

2. **Sack Logic**: When a mon is at ≤20% HP and would normally switch out,
   DON'T — let it die for free switch-in rather than wasting a turn.

3. **Pivot Moves**: U-turn / Volt Switch instead of raw switch when they
   deal at least neutral damage. Chip + reposition in one action.

Conservative design: each feature only fires under strict conditions.
When no special condition is met, V10 behaves exactly like V8.
"""

from __future__ import annotations

from poke_env.environment.move_category import MoveCategory

from ...core.base import BaseHeuristic1v1
from ...core.common import get_status_name

SPEED_TIER_COEFF = 0.1
HP_FRACTION_COEFF = 0.4
SWITCH_OUT_MATCHUP_THRESHOLD = -2
WEAK_MOVE_THRESHOLD = 30

STATUS_MOVE_THRESHOLD = 40
HIGH_HP_FRACTION = 0.7
SAC_HP_THRESHOLD = 0.2

ABILITY_IMMUNITIES = {
    "flashfire": "FIRE",
    "levitate": "GROUND",
    "voltabsorb": "ELECTRIC",
    "lightningrod": "ELECTRIC",
    "waterabsorb": "WATER",
    "stormdrain": "WATER",
    "dryskin": "WATER",
    "sapsipper": "GRASS",
    "motordrive": "ELECTRIC",
}


class HeuristicV10(BaseHeuristic1v1):
    """V8 core + status moves + sack logic + pivot moves."""

    @property
    def tracks_moves(self) -> bool:
        return True

    # -- Priority KO Hook (same as V8) ----------------------------------------

    def _pre_move_hook(self, battle):
        me = battle.active_pokemon
        opp = battle.opponent_active_pokemon

        if not battle.available_moves or me is None or opp is None:
            return None

        opp_hp_fraction = opp.current_hp_fraction
        if opp_hp_fraction <= 0:
            return None

        my_status = get_status_name(me)

        priority_moves = [
            m for m in battle.available_moves
            if m.entry.get("priority", 0) > 0 and m.base_power > 0
        ]
        if not priority_moves:
            return None

        physical_ratio = self._stat_estimation(me, "atk") / max(self._stat_estimation(opp, "def"), 1.0)
        special_ratio = self._stat_estimation(me, "spa") / max(self._stat_estimation(opp, "spd"), 1.0)

        if my_status == "BRN":
            physical_ratio *= 0.5

        for move in priority_moves:
            if self._is_ability_immune(move, opp):
                continue

            if move.category == MoveCategory.PHYSICAL:
                ratio = physical_ratio
            elif move.category == MoveCategory.SPECIAL:
                ratio = special_ratio
            else:
                continue

            effectiveness = opp.damage_multiplier(move)
            stab = 1.5 if move.type in me.types else 1.0
            expected_hits = move.expected_hits if hasattr(move, "expected_hits") else 1.0

            raw = (0.44 * move.base_power * ratio + 2) * stab * effectiveness * expected_hits
            dmg_fraction = raw / 300.0

            if dmg_fraction >= opp_hp_fraction * 2.0:
                btag = battle.battle_tag
                self._ko_checks_by_battle[btag] = self._ko_checks_by_battle.get(btag, 0) + 1
                self._record_used_move(btag, move.id)
                return self.create_order(move)

        return None

    # -- Main Decision Logic ---------------------------------------------------

    def _select_action(self, battle):
        me = battle.active_pokemon
        opp = battle.opponent_active_pokemon

        if me is None or opp is None:
            return None

        my_status = get_status_name(me)
        opp_status = get_status_name(opp)
        my_speed = self._get_boosted_speed(me, my_status)
        opp_speed = self._get_boosted_speed(opp, opp_status)

        # 1. Score all damaging moves (boost-aware)
        best_move = None
        max_score = -1.0

        physical_ratio = self._stat_estimation(me, "atk") / max(self._stat_estimation(opp, "def"), 1.0)
        special_ratio = self._stat_estimation(me, "spa") / max(self._stat_estimation(opp, "spd"), 1.0)

        if my_status == "BRN":
            physical_ratio *= 0.5

        for move in battle.available_moves or []:
            if self._is_ability_immune(move, opp):
                continue
            score = self._score_move(move, me, opp, physical_ratio, special_ratio, battle, my_speed, opp_speed)
            if score > max_score:
                max_score, best_move = score, move

        # 2. Check if we should switch
        switch_reason = ""
        if battle.available_switches:
            switch_reason = self._should_switch(me, opp, my_status, my_speed, opp_speed, max_score, battle)

        # 3. Switch logic with sack and pivot
        if switch_reason:
            if me.current_hp_fraction <= SAC_HP_THRESHOLD and switch_reason != "toxic":
                pass
            else:
                pivot = self._find_pivot_move(battle, me, opp)
                if pivot:
                    btag = battle.battle_tag
                    self._matchup_switches_by_battle[btag] = self._matchup_switches_by_battle.get(btag, 0) + 1
                    self._record_used_move(btag, pivot.id)
                    return self.create_order(pivot)

                switch = self._get_best_switch(battle, opp)
                if switch:
                    if switch_reason == "matchup":
                        btag = battle.battle_tag
                        self._matchup_switches_by_battle[btag] = self._matchup_switches_by_battle.get(btag, 0) + 1
                    return self.create_order(switch)

        # 4. Status move logic (when we can't break opponent)
        if max_score < STATUS_MOVE_THRESHOLD and opp.current_hp_fraction >= HIGH_HP_FRACTION:
            status_move = self._find_best_status_move(battle, me, opp, my_speed, opp_speed)
            if status_move:
                self._record_used_move(battle.battle_tag, status_move.id)
                return self.create_order(status_move)

        # 5. Attack with best move
        if best_move:
            self._record_used_move(battle.battle_tag, best_move.id)
            return self.create_order(best_move)

        return None

    # -- Pivot Move Detection --------------------------------------------------

    def _find_pivot_move(self, battle, me, opp):
        """Return a pivot move (U-turn/Volt Switch) if it deals neutral+ damage."""
        for move in battle.available_moves or []:
            if move.self_switch is not True:
                continue
            if move.base_power < 1:
                continue
            if self._is_ability_immune(move, opp):
                continue
            effectiveness = opp.damage_multiplier(move)
            if effectiveness >= 1.0:
                return move
        return None

    # -- Status Move Selection -------------------------------------------------

    def _find_best_status_move(self, battle, me, opp, my_speed, opp_speed):
        """Pick Toxic/WoW/TWave if conditions are strictly met."""
        if opp.status is not None:
            return None

        opp_types = [t.name for t in opp.types if t is not None]
        best_status = None
        best_priority = -1

        for move in battle.available_moves or []:
            if move.base_power > 0:
                continue
            if move.status is None:
                continue

            accuracy = move.accuracy if isinstance(move.accuracy, (int, float)) else 1.0
            if accuracy < 0.5:
                continue

            status_name = move.status.name
            priority = 0

            if status_name == "TOX" or status_name == "PSN":
                if "STEEL" in opp_types or "POISON" in opp_types:
                    continue
                priority = 3

            elif status_name == "BRN":
                if "FIRE" in opp_types:
                    continue
                if not self._is_physical_attacker(opp):
                    continue
                priority = 2

            elif status_name == "PAR":
                if "GROUND" in opp_types or "ELECTRIC" in opp_types:
                    continue
                if my_speed >= opp_speed:
                    continue
                priority = 1

            else:
                continue

            if priority > best_priority:
                best_priority = priority
                best_status = move

        return best_status

    # -- Move Scoring (boost-aware, same as V8) --------------------------------

    def _score_move(self, move, me, opp, physical_ratio, special_ratio, battle, my_speed, opp_speed) -> float:
        if move.base_power <= 1:
            return 0.0

        if move.category == MoveCategory.PHYSICAL:
            ratio = physical_ratio
        elif move.category == MoveCategory.SPECIAL:
            ratio = special_ratio
        else:
            return 0.0

        effectiveness = opp.damage_multiplier(move)
        stab = 1.5 if move.type in me.types else 1.0
        accuracy = move.accuracy if isinstance(move.accuracy, (int, float)) else 1.0
        expected_hits = move.expected_hits if hasattr(move, "expected_hits") else 1.0

        score = move.base_power * ratio * effectiveness * stab * accuracy * expected_hits

        score = self._apply_weather_mod(score, move, battle)
        score = self._apply_terrain_mod(score, move, battle)

        if move.entry.get("priority", 0) > 0 and my_speed < opp_speed:
            score *= 1.3

        return float(score)

    # -- Switch Decision (same as V8) ------------------------------------------

    def _should_switch(self, me, opp, my_status, my_speed, opp_speed, max_score, battle) -> str:
        if my_status == "TOX" and me.status_counter > 2:
            return "toxic"

        if max_score < WEAK_MOVE_THRESHOLD and my_speed < opp_speed:
            return "weak"

        has_good_switch = any(
            self._estimate_matchup(s, opp) > 0 for s in battle.available_switches
        )
        if not has_good_switch:
            return ""

        if me.boosts.get("def", 0) <= -3 or me.boosts.get("spd", 0) <= -3:
            return "matchup"

        if me.boosts.get("atk", 0) <= -3 and self._is_physical_attacker(me):
            return "matchup"
        if me.boosts.get("spa", 0) <= -3 and not self._is_physical_attacker(me):
            return "matchup"

        if self._estimate_matchup(me, opp) < SWITCH_OUT_MATCHUP_THRESHOLD:
            return "matchup"

        return ""

    @staticmethod
    def _is_physical_attacker(mon) -> bool:
        atk = mon.base_stats.get("atk", 100) if mon.base_stats else 100
        spa = mon.base_stats.get("spa", 100) if mon.base_stats else 100
        return atk >= spa

    # -- Switch Target Selection -----------------------------------------------

    def _get_best_switch(self, battle, opp):
        best = None
        best_score = -999.0

        for pokemon in battle.available_switches:
            score = self._estimate_matchup(pokemon, opp)
            if score > best_score:
                best_score = score
                best = pokemon

        return best if best_score > -1.0 else battle.available_switches[0]

    # -- Matchup Estimation ----------------------------------------------------

    @staticmethod
    def _estimate_matchup(mon, opponent) -> float:
        mon_types = [t for t in mon.types if t is not None]
        opp_types = [t for t in opponent.types if t is not None]

        if not mon_types or not opp_types:
            return 0.0

        score = max(opponent.damage_multiplier(t) for t in mon_types)
        score -= max(mon.damage_multiplier(t) for t in opp_types)

        mon_speed = mon.base_stats.get("spe", 100) if mon.base_stats else 100
        opp_speed = opponent.base_stats.get("spe", 100) if opponent.base_stats else 100
        if mon_speed > opp_speed:
            score += SPEED_TIER_COEFF
        elif opp_speed > mon_speed:
            score -= SPEED_TIER_COEFF

        score += mon.current_hp_fraction * HP_FRACTION_COEFF
        score -= opponent.current_hp_fraction * HP_FRACTION_COEFF

        return score

    # -- Stat Estimation (boost-aware) -----------------------------------------

    @staticmethod
    def _stat_estimation(mon, stat: str) -> float:
        base = mon.base_stats.get(stat, 100) if mon.base_stats else 100
        boost = mon.boosts.get(stat, 0)
        if boost > 0:
            multiplier = (2.0 + boost) / 2.0
        elif boost < 0:
            multiplier = 2.0 / (2.0 - boost)
        else:
            multiplier = 1.0
        return ((2.0 * base + 31.0) + 5.0) * multiplier

    @staticmethod
    def _get_boosted_speed(mon, status: str) -> float:
        base = mon.base_stats.get("spe", 100) if mon.base_stats else 100
        boost = mon.boosts.get("spe", 0)
        if boost > 0:
            multiplier = (2.0 + boost) / 2.0
        elif boost < 0:
            multiplier = 2.0 / (2.0 - boost)
        else:
            multiplier = 1.0
        speed = base * multiplier
        if status == "PAR":
            speed *= 0.5
        return speed

    # -- Ability Immunity (only when known) ------------------------------------

    @staticmethod
    def _is_ability_immune(move, defender) -> bool:
        ability = getattr(defender, "ability", None)
        if not ability:
            return False
        ability_str = str(ability).lower().replace(" ", "").replace("-", "")
        immune_type = ABILITY_IMMUNITIES.get(ability_str)
        if immune_type and move.type.name == immune_type:
            return True
        return False

    # -- Weather/Terrain Modifiers ---------------------------------------------

    @staticmethod
    def _apply_weather_mod(damage: float, move, battle) -> float:
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
    def _apply_terrain_mod(damage: float, move, battle) -> float:
        if not battle.fields:
            return damage
        move_type = move.type.name
        terrain_boosts = {"ELECTRIC": "ELECTRIC", "GRASSY": "GRASS", "PSYCHIC": "PSYCHIC"}
        for field in battle.fields:
            f_name = str(field).upper()
            for terrain_key, boosted_type in terrain_boosts.items():
                if terrain_key in f_name and move_type == boosted_type:
                    damage *= 1.3
        return damage
