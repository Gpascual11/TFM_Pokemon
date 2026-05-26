"""Heuristic V11: Anti-Abyssal Meta Master.

The ultimate hybrid agent, combining the strengths of V9 and V10:
1. V10's Tactical Logic: Priority KO checks, Status moves, Sack logic, Pivot moves, Ability immunity.
2. V9's Strategic Logic: Tight Hazards and Tight Setup on free turns.
3. Gen-Aware Adaptation:
   - Disable hazards and setup in Generation 1.
   - Adjust Paralysis speed drop (75% drop in Gen 1-6, 50% drop in Gen 7+).
"""

from __future__ import annotations

from poke_env.environment.move_category import MoveCategory
from poke_env.environment.side_condition import SideCondition

from ...core.base import BaseHeuristic1v1
from ...core.common import get_status_name

SPEED_TIER_COEFF = 0.1
HP_FRACTION_COEFF = 0.4
SWITCH_OUT_MATCHUP_THRESHOLD = -2
WEAK_MOVE_THRESHOLD = 30

STATUS_MOVE_THRESHOLD = 40
HIGH_HP_FRACTION = 0.7
SAC_HP_THRESHOLD = 0.2

ENTRY_HAZARDS = {
    "spikes": SideCondition.SPIKES,
    "stealthrock": SideCondition.STEALTH_ROCK,
    "stickyweb": SideCondition.STICKY_WEB,
    "toxicspikes": SideCondition.TOXIC_SPIKES,
}
ANTI_HAZARDS_MOVES = {"rapidspin", "defog"}

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


class HeuristicV11(BaseHeuristic1v1):
    """V11 Hybrid Agent: V10 tactical logic + V9 hazard/setup logic + Gen adaptation."""

    @property
    def tracks_moves(self) -> bool:
        return True

    # -- Priority KO Hook (V10 core) ------------------------------------------

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

        format_str = battle._format or ""
        is_gen1 = "gen1" in format_str

        my_status = get_status_name(me)
        opp_status = get_status_name(opp)
        my_speed = self._get_boosted_speed(me, my_status, format_str)
        opp_speed = self._get_boosted_speed(opp, opp_status, format_str)

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
            can_sack = (
                me.current_hp_fraction <= SAC_HP_THRESHOLD
                and me.current_hp_fraction > 0
                and switch_reason == "matchup"
                and battle.available_moves
                and max_score >= WEAK_MOVE_THRESHOLD
            )
            if can_sack:
                # Let the Pokemon stay in and be sacrificed for a free switch-in
                pass
            else:
                pivot = self._find_pivot_move(battle, me, opp, format_str)
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

        # 4. Hazards: ONLY on free turns (disabled in Gen 1)
        if not is_gen1 and my_speed > opp_speed and self._resists_opp_stab(me, opp):
            hazard_order = self._try_hazards(battle)
            if hazard_order:
                return hazard_order

        # 5. Setup: ONLY at full HP + positive matchup (disabled in Gen 1)
        if not is_gen1 and me.current_hp_fraction == 1.0 and self._estimate_matchup(me, opp) > 0:
            setup_order = self._try_setup(battle, me)
            if setup_order:
                return setup_order

        # 6. Status move logic (when we can't break opponent)
        if max_score < STATUS_MOVE_THRESHOLD and opp.current_hp_fraction >= HIGH_HP_FRACTION:
            status_move = self._find_best_status_move(battle, me, opp, my_speed, opp_speed)
            if status_move:
                self._record_used_move(battle.battle_tag, status_move.id)
                return self.create_order(status_move)

        # 7. Attack with best move
        if best_move:
            self._record_used_move(battle.battle_tag, best_move.id)
            return self.create_order(best_move)

        return None

    # -- Pivot Move Detection --------------------------------------------------

    def _find_pivot_move(self, battle, me, opp, format_str: str):
        """Return a pivot move (U-turn/Volt Switch) if we're faster and it deals neutral+ damage."""
        my_speed = self._get_boosted_speed(me, get_status_name(me), format_str)
        opp_speed = self._get_boosted_speed(opp, get_status_name(opp), format_str)
        if my_speed <= opp_speed:
            return None

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

    # -- Hazard Logic (V9) -----------------------------------------------------

    def _try_hazards(self, battle) -> object:
        """Set hazards or clear own. Only called on verified free turns."""
        if not battle.available_moves:
            return None

        btag = battle.battle_tag
        n_opp_remaining = 6 - len([m for m in battle.opponent_team.values() if m.fainted])
        n_remaining = len([m for m in battle.team.values() if not m.fainted])

        if n_opp_remaining >= 3:
            for move in battle.available_moves:
                if move.id in ENTRY_HAZARDS:
                    condition = ENTRY_HAZARDS[move.id]
                    if condition not in battle.opponent_side_conditions:
                        self._hazard_sets_by_battle[btag] = self._hazard_sets_by_battle.get(btag, 0) + 1
                        self._record_used_move(btag, move.id)
                        return self.create_order(move)

        if battle.side_conditions and n_remaining >= 2:
            for move in battle.available_moves:
                if move.id in ANTI_HAZARDS_MOVES:
                    self._hazard_removals_by_battle[btag] = self._hazard_removals_by_battle.get(btag, 0) + 1
                    self._record_used_move(btag, move.id)
                    return self.create_order(move)

        return None

    # -- Setup Logic (V9) ------------------------------------------------------

    def _try_setup(self, battle, me) -> object:
        """Use a boost move. Only called when at full HP with good matchup."""
        for move in battle.available_moves or []:
            if not move.boosts or move.target != "self":
                continue
            boost_sum = sum(v for v in move.boosts.values() if v > 0)
            if boost_sum < 2:
                continue
            min_current = min(
                me.boosts.get(s, 0) for s, v in move.boosts.items() if v > 0
            )
            if min_current >= 6:
                continue
            btag = battle.battle_tag
            self._setup_uses_by_battle[btag] = self._setup_uses_by_battle.get(btag, 0) + 1
            self._record_used_move(btag, move.id)
            return self.create_order(move)

        return None

    @staticmethod
    def _resists_opp_stab(me, opp) -> bool:
        """Check if we resist all of opponent's STAB types."""
        opp_types = [t for t in opp.types if t is not None]
        if not opp_types:
            return False
        max_threat = max(me.damage_multiplier(t) for t in opp_types)
        return max_threat <= 1.0

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

    # -- Move Scoring (boost-aware, V8 core) -----------------------------------

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

    def _get_boosted_speed(self, mon, status: str, format_str: str) -> float:
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
            # Gen 1-6: Paralysis reduces speed by 75% (0.25 multiplier).
            # Gen 7+: Paralysis reduces speed by 50% (0.5 multiplier).
            is_gen7_or_later = any(g in format_str for g in ["gen7", "gen8", "gen9"])
            par_multiplier = 0.5 if is_gen7_or_later else 0.25
            speed *= par_multiplier
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
