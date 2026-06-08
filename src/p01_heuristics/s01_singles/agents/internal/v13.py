"""Heuristic V13: Advanced Matchup Optimizer.

Extends HeuristicV12 with:
1. Move-Aware Matchup Estimation: Estimates matchups using actual moves rather than just types.
2. Dynamic Mid-Battle Switching: Allows switching when active matchup is poor and a far superior bench option exists.
3. Strict Immunity/Effectiveness Check: Explicitly rejects moves with 0 effectiveness against the opponent.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from poke_env.data import GenData
from poke_env.environment.move_category import MoveCategory
from poke_env.environment.side_condition import SideCondition
from poke_env.environment.pokemon_type import PokemonType

from ...core.base import BaseHeuristic1v1
from ...core.common import get_status_name

SPEED_TIER_COEFF = 0.1
HP_FRACTION_COEFF = 0.4
SWITCH_OUT_MATCHUP_THRESHOLD = -2.0
WEAK_MOVE_THRESHOLD = 30.0

STATUS_MOVE_THRESHOLD = 40.0
HIGH_HP_FRACTION = 0.7
SAC_HP_THRESHOLD = 0.2

ENTRY_HAZARDS = {
    "spikes": SideCondition.SPIKES,
    "stealthrock": SideCondition.STEALTH_ROCK,
    "stickyweb": SideCondition.STICKY_WEB,
    "toxicspikes": SideCondition.TOXIC_SPIKES,
}
ANTI_HAZARDS_MOVES = {"rapidspin", "defog", "tidyup", "courtchange"}

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

RECOVERY_MOVES = {"recover", "roost", "slackoff", "softboiled", "moonlight", "synthesis", "milkdrink", "shoreup"}
DRAINING_MOVES = {"gigadrain", "drainpunch", "hornleech", "bitterblade", "drainingkiss", "leechlife", "paraboliccharge"}

_POKEMON_SETS_CACHE: dict[int, dict] = {}


class HeuristicV13(BaseHeuristic1v1):
    """V13 Hybrid Agent: Heuristic V12 + Dynamic Switching & Move-Aware Matchup Estimation."""

    @property
    def tracks_moves(self) -> bool:
        return True

    def _get_gen(self, battle) -> int:
        if battle is None:
            return 9
        format_str = getattr(battle, "_format", "") or ""
        if format_str.startswith("gen"):
            try:
                return int(format_str[3])
            except (IndexError, ValueError):
                pass
        return 9

    def _load_pokemon_sets(self, gen: int) -> dict:
        global _POKEMON_SETS_CACHE
        if gen in _POKEMON_SETS_CACHE:
            return _POKEMON_SETS_CACHE[gen]

        sets_dict = {}
        try:
            # Go up 5 parents to get to workspace root
            workspace_root = Path(__file__).resolve().parents[5]
            showdown_dir = workspace_root / "pokemon-showdown" / "data" / "random-battles"

            if gen in [8, 1]:
                path = showdown_dir / f"gen{gen}" / "data.json"
                if path.exists():
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    for mon_name, mon_data in data.items():
                        moves = set()
                        for key in ["moves", "essentialMoves", "exclusiveMoves", "comboMoves", "noDynamaxMoves"]:
                            if key in mon_data:
                                for m in mon_data[key]:
                                    moves.add(m.lower().replace(" ", "").replace("-", ""))
                        clean_mon_name = mon_name.lower().replace(" ", "").replace("-", "").replace("_", "")
                        sets_dict[clean_mon_name] = {
                            "moves": list(moves),
                            "abilities": [],
                            "teraTypes": []
                        }
            else:
                path = showdown_dir / f"gen{gen}" / "sets.json"
                if path.exists():
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    for mon_name, mon_data in data.items():
                        moves = set()
                        abilities = set()
                        tera_types = set()
                        if "sets" in mon_data:
                            for s in mon_data["sets"]:
                                if "movepool" in s:
                                    for m in s["movepool"]:
                                        moves.add(m.lower().replace(" ", "").replace("-", ""))
                                if "abilities" in s:
                                    for ab in s["abilities"]:
                                        abilities.add(ab.lower().replace(" ", "").replace("-", ""))
                                if "teraTypes" in s:
                                    for t in s["teraTypes"]:
                                        tera_types.add(t.upper())
                        clean_mon_name = mon_name.lower().replace(" ", "").replace("-", "").replace("_", "")
                        sets_dict[clean_mon_name] = {
                            "moves": list(moves),
                            "abilities": list(abilities),
                            "teraTypes": list(tera_types)
                        }
        except Exception:
            pass

        _POKEMON_SETS_CACHE[gen] = sets_dict
        return sets_dict

    # -- Team Preview (Lead Selection) ----------------------------------------

    def teampreview(self, battle) -> str:
        """Returns the team order, maximizing matchup score of the lead."""
        team_list = list(battle.team.values())
        if not team_list:
            return self.random_teampreview(battle)

        opp_team_list = list(battle.opponent_team.values()) if battle.opponent_team else []

        if not opp_team_list:
            # Opponent team is hidden, sort by speed descending
            sorted_team = sorted(
                enumerate(team_list),
                key=lambda x: x[1].base_stats.get("spe", 100) if x[1].base_stats else 100,
                reverse=True
            )
        else:
            # Calculate average matchup for each teammate
            teammate_scores = []
            for i, mon in enumerate(team_list):
                total_score = 0.0
                for opp in opp_team_list:
                    total_score += self._estimate_matchup(mon, opp, battle)
                avg_score = total_score / len(opp_team_list)
                teammate_scores.append((avg_score, i, mon))

            # Sort teammates by average score descending.
            # If scores are equal, sort by speed descending.
            sorted_team_info = sorted(
                teammate_scores,
                key=lambda x: (x[0], x[2].base_stats.get("spe", 100) if x[2].base_stats else 100),
                reverse=True
            )
            sorted_team = [(idx, mon) for (score, idx, mon) in sorted_team_info]

        order_str = "".join(str(idx + 1) for idx, _ in sorted_team)
        return "/team " + order_str

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
            if opp.damage_multiplier(move) == 0.0:
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
                # Check for terastallization
                tera = False
                if move.base_power > 0:
                    tera = self._should_terastallize(battle, move)
                return self.create_order(move, terastallize=tera)

        return None

    def _predict_and_punish_switch(self, battle, me, opp, best_move, physical_ratio, special_ratio, my_speed, opp_speed) -> Any:
        active_matchup = self._estimate_matchup(me, opp, battle)

        # Opponent is likely to switch if they are in a terrible matchup
        if active_matchup < 0.8:
            return None

        # Find their best benched counter-pick
        predicted_switch_in = None
        best_opp_bench_score = -999.0
        for s in battle.opponent_team.values():
            if s.fainted or s.active:
                continue
            # Matchup score of benched opponent mon vs me
            score = self._estimate_matchup(s, me, battle)
            if score > best_opp_bench_score:
                best_opp_bench_score = score
                predicted_switch_in = s

        # Only predict if they have a highly viable bench option
        if not predicted_switch_in or best_opp_bench_score < 0.2:
            return None

        # Check if our best_move is resisted or immune by the predicted switch-in
        mult_against_switch_in = predicted_switch_in.damage_multiplier(best_move)
        if mult_against_switch_in > 0.5:
            # Our best move is still effective enough, no need to predict-switch
            return None

        # Look for a coverage move that hits the switch-in effectively and does OK damage to current opp
        best_prediction_move = None
        max_prediction_score = -1.0

        for move in battle.available_moves or []:
            if move.base_power <= 1:
                continue
            if self._is_ability_immune(move, predicted_switch_in):
                continue
            if self._is_ability_immune(move, opp):
                continue

            # Type multiplier against both
            mult_switch = predicted_switch_in.damage_multiplier(move)
            mult_current = opp.damage_multiplier(move)

            # We want a move that hits the switch-in for neutral/super-effective (>= 1.0)
            # and doesn't do 0 to the current active
            if mult_switch >= 1.0 and mult_current > 0.0:
                score = self._score_move(
                    move, me, predicted_switch_in, physical_ratio, special_ratio, battle, my_speed, opp_speed
                )
                if score > max_prediction_score:
                    max_prediction_score = score
                    best_prediction_move = move

        if best_prediction_move and best_prediction_move != best_move:
            return best_prediction_move

        return None

    def _handle_opponent_setup_sweeper(self, battle, me, opp, my_speed, opp_speed):
        opp_atk_boost = opp.boosts.get("atk", 0)
        opp_spa_boost = opp.boosts.get("spa", 0)
        opp_spe_boost = opp.boosts.get("spe", 0)

        if max(opp_atk_boost, opp_spa_boost) >= 1 or opp_spe_boost >= 1:
            # Check Haze / Clear Smog
            for move in battle.available_moves:
                if move.id in {"haze", "clearsmog"}:
                    self._record_used_move(battle.battle_tag, move.id)
                    return self.create_order(move)

            # Check Phazing
            if opp_speed < my_speed or me.current_hp_fraction > 0.4:
                for move in battle.available_moves:
                    if move.id in {"roar", "whirlwind", "dragontail", "circlethrow"}:
                        self._record_used_move(battle.battle_tag, move.id)
                        return self.create_order(move)

            # Cripple with status
            if opp.status is None:
                for move in battle.available_moves:
                    if move.id == "willowisp" and opp_atk_boost >= 1:
                        self._record_used_move(battle.battle_tag, move.id)
                        return self.create_order(move)
                    if move.id in {"thunderwave", "glare", "nuzzle"} and (opp_spe_boost >= 1 or opp_speed > my_speed):
                        self._record_used_move(battle.battle_tag, move.id)
                        return self.create_order(move)
                    if move.id in {"toxic", "yawn"}:
                        self._record_used_move(battle.battle_tag, move.id)
                        return self.create_order(move)

            # Encore locking
            if "encore" in [m.id for m in battle.available_moves] and my_speed > opp_speed:
                for move in battle.available_moves:
                    if move.id == "encore":
                        self._record_used_move(battle.battle_tag, move.id)
                        return self.create_order(move)

        return None

    # -- Main Decision Logic ---------------------------------------------------

    def _select_action(self, battle):
        me = battle.active_pokemon
        opp = battle.opponent_active_pokemon

        # 0. Fainted Switch / Forced Switch / No Available Moves
        force_switch = battle.force_switch
        if isinstance(force_switch, list):
            force_switch = any(force_switch)

        if force_switch or me is None or me.fainted or not battle.available_moves:
            if battle.available_switches:
                if opp is not None and not opp.fainted:
                    switch = self._get_best_switch(battle, opp)
                else:
                    switch = self._get_best_switch_double_faint(battle)
                if switch:
                    return self.create_order(switch)
            return None

        format_str = battle._format or ""
        is_gen1 = "gen1" in format_str

        my_status = get_status_name(me)
        opp_status = get_status_name(opp)
        my_speed = self._get_boosted_speed(me, my_status, format_str)
        opp_speed = self._get_boosted_speed(opp, opp_status, format_str)

        # 0b. Opponent Setup Sweeper Check
        setup_reaction = self._handle_opponent_setup_sweeper(battle, me, opp, my_speed, opp_speed)
        if setup_reaction:
            return setup_reaction

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

        # 3b. Smart Recovery Check
        recovery_moves = [m for m in battle.available_moves if m.id in RECOVERY_MOVES]
        if recovery_moves and me.current_hp_fraction <= 0.6:
            gen = self._get_gen(battle)
            sets_db = self._load_pokemon_sets(gen)
            opp_max_dmg = self._estimate_max_damage(opp, me, gen, sets_db)
            opp_max_dmg_fraction = opp_max_dmg / 300.0

            if opp_max_dmg_fraction < me.current_hp_fraction:
                can_ko = False
                if best_move and best_move.base_power > 0:
                    best_dmg = self._score_move(best_move, me, opp, physical_ratio, special_ratio, battle, my_speed, opp_speed)
                    best_dmg_fraction = best_dmg / 300.0
                    if best_dmg_fraction >= opp.current_hp_fraction:
                        can_ko = True

                if not can_ko:
                    rec_move = recovery_moves[0]
                    self._record_used_move(battle.battle_tag, rec_move.id)
                    return self.create_order(rec_move)

        # 4. Hazards: on free turns, turn 1, or when opponent is highly likely to switch (disabled in Gen 1)
        if not is_gen1:
            active_matchup = self._estimate_matchup(me, opp, battle)
            opp_likely_to_switch = active_matchup > 1.0
            is_free_turn = my_speed > opp_speed and self._resists_opp_stab(me, opp)
            if is_free_turn or battle.turn == 1 or opp_likely_to_switch:
                hazard_order = self._try_hazards(battle)
                if hazard_order:
                    return hazard_order

        # 5. Setup: ONLY at full HP + positive matchup (disabled in Gen 1)
        if not is_gen1 and me.current_hp_fraction == 1.0 and self._estimate_matchup(me, opp, battle) > 0:
            setup_order = self._try_setup(battle, me)
            if setup_order:
                return setup_order

        # 6. Status move logic (when we can't break opponent)
        if max_score < STATUS_MOVE_THRESHOLD and opp.current_hp_fraction >= HIGH_HP_FRACTION:
            status_move = self._find_best_status_move(battle, me, opp, my_speed, opp_speed)
            if status_move:
                self._record_used_move(battle.battle_tag, status_move.id)
                return self.create_order(status_move)

        # 7. Attack with best move (with predictive switch punishment check)
        if best_move:
            punish_move = self._predict_and_punish_switch(
                battle, me, opp, best_move, physical_ratio, special_ratio, my_speed, opp_speed
            )
            selected_move = punish_move if punish_move else best_move
            self._record_used_move(battle.battle_tag, selected_move.id)
            tera = False
            if selected_move.base_power > 0:
                tera = self._should_terastallize(battle, selected_move)
            return self.create_order(selected_move, terastallize=tera)

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
        """Pick Sleep/Toxic/WoW/TWave if conditions are strictly met."""
        if opp.status is not None:
            return None

        opp_types = [t.name for t in opp.types if t is not None]
        best_status = None
        best_priority = -1

        opp_has_sleep = any(get_status_name(m) == "SLP" for m in battle.opponent_team.values())

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

            if status_name == "SLP":
                if opp_has_sleep:
                    continue
                priority = 4

            elif status_name == "TOX" or status_name == "PSN":
                if "STEEL" in opp_types or "POISON" in opp_types:
                    continue
                opp_ability = str(getattr(opp, "ability", "")).lower()
                if "guts" in opp_ability:
                    continue
                priority = 3

            elif status_name == "BRN":
                if "FIRE" in opp_types:
                    continue
                if not self._is_physical_attacker(opp):
                    continue
                opp_ability = str(getattr(opp, "ability", "")).lower()
                if "guts" in opp_ability:
                    continue
                priority = 2

            elif status_name == "PAR":
                if "GROUND" in opp_types or "ELECTRIC" in opp_types:
                    continue
                if my_speed >= opp_speed:
                    continue
                opp_ability = str(getattr(opp, "ability", "")).lower()
                if "guts" in opp_ability:
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
        if effectiveness == 0.0:
            return 0.0

        stab = 1.5 if move.type in me.types else 1.0
        accuracy = move.accuracy if isinstance(move.accuracy, (int, float)) else 1.0
        expected_hits = move.expected_hits if hasattr(move, "expected_hits") else 1.0

        score = move.base_power * ratio * effectiveness * stab * accuracy * expected_hits

        score = self._apply_weather_mod(score, move, battle)
        score = self._apply_terrain_mod(score, move, battle)

        if move.entry.get("priority", 0) > 0 and my_speed < opp_speed:
            score *= 1.3

        if move.id in DRAINING_MOVES and me.current_hp_fraction < 0.9:
            score *= 1.15

        is_clearing_move = move.id in {"rapidspin", "tidyup"}
        if is_clearing_move:
            has_hazards = any(c in battle.side_conditions for c in ENTRY_HAZARDS.values())
            n_bench_alive = len([m for m in battle.team.values() if not m.fainted and m != me])
            if has_hazards and n_bench_alive > 0:
                opp_hp = opp.current_hp_fraction
                if opp_hp > 0.2:
                    score += 80.0

        return float(score)

    # -- Switch Decision (smarter mid-battle logic) ----------------------------

    def _should_switch(self, me, opp, my_status, my_speed, opp_speed, max_score, battle) -> str:
        if my_status == "TOX" and me.status_counter > 2:
            return "toxic"

        if max_score < WEAK_MOVE_THRESHOLD and my_speed < opp_speed:
            return "weak"

        # Calculate best score of any switch-in option
        best_bench_score = -999.0
        for s in battle.available_switches:
            bench_score = self._estimate_matchup(s, opp, battle)
            if bench_score > best_bench_score:
                best_bench_score = bench_score

        active_matchup = self._estimate_matchup(me, opp, battle)

        # Dynamic mid-battle switching triggers:
        # 1. We have a highly favorable bench option (> 0.5) AND our active matchup is neutral/unfavorable (< 0.1)
        #    or we can only deal weak damage (max_score < STATUS_MOVE_THRESHOLD).
        if best_bench_score > 0.5:
            if active_matchup < 0.1:
                return "matchup"
            if max_score < STATUS_MOVE_THRESHOLD:
                return "matchup"

        # 2. Our current matchup is bad (< -0.8) and we have a bench option that is significantly better (+0.6 points)
        if active_matchup < -0.8 and best_bench_score > active_matchup + 0.6:
            return "matchup"

        # Stat drops checks
        if me.boosts.get("def", 0) <= -3 or me.boosts.get("spd", 0) <= -3:
            return "matchup"

        if me.boosts.get("atk", 0) <= -3 and self._is_physical_attacker(me):
            return "matchup"
        if me.boosts.get("spa", 0) <= -3 and not self._is_physical_attacker(me):
            return "matchup"

        # Hard fallback threshold
        if active_matchup < SWITCH_OUT_MATCHUP_THRESHOLD:
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

        # Check if opponent is choice-locked
        opp_item = str(opp.item).lower() if opp.item else ""
        is_choice_locked = "choice" in opp_item and len(opp.moves) > 0

        for pokemon in battle.available_switches:
            score = self._estimate_matchup(pokemon, opp, battle)

            # Choice lock exploitation: if opponent is choice-locked and this switch-in resists/is immune to all revealed opponent moves
            if is_choice_locked:
                all_resisted = True
                for opp_move in opp.moves.values():
                    if opp_move.base_power > 0:
                        eff = pokemon.damage_multiplier(opp_move)
                        if eff >= 1.0:
                            all_resisted = False
                            break
                if all_resisted:
                    score += 1.5  # Massive bonus for a safe switch-in!

            if score > best_score:
                best_score = score
                best = pokemon

        return best if best is not None else battle.available_switches[0]

    def _get_best_switch_double_faint(self, battle) -> Any:
        if not battle.available_switches:
            return None
        opp_remaining = [p for p in battle.opponent_team.values() if not p.fainted]
        if not opp_remaining:
            return max(
                battle.available_switches,
                key=lambda x: x.base_stats.get("spe", 100) if x.base_stats else 100
            )

        best = None
        best_score = -999.0
        for mon in battle.available_switches:
            total_score = 0.0
            for opp in opp_remaining:
                total_score += self._estimate_matchup(mon, opp, battle)
            avg_score = total_score / len(opp_remaining)
            if avg_score > best_score:
                best_score = avg_score
                best = mon
        return best if best is not None else battle.available_switches[0]

    # -- Terastallization (Gen 9) ----------------------------------------------

    def _get_tera_type(self, pokemon) -> PokemonType | None:
        if hasattr(pokemon, "tera_type") and pokemon.tera_type is not None:
            if isinstance(pokemon.tera_type, str):
                try:
                    return PokemonType.from_name(pokemon.tera_type)
                except:
                    pass
            elif isinstance(pokemon.tera_type, PokemonType):
                return pokemon.tera_type

        if hasattr(pokemon, "guess_tera"):
            t_str = pokemon.guess_tera()
            if t_str:
                try:
                    return PokemonType.from_name(t_str)
                except:
                    pass

        if getattr(pokemon, "_terastallized_type", None) is not None:
            return pokemon._terastallized_type

        return None

    def _should_terastallize(self, battle, move) -> bool:
        try:
            active = battle.active_pokemon
            opp_active = battle.opponent_active_pokemon
            if not getattr(battle, "can_tera", False) or not active or not opp_active:
                return False

            if move.base_power <= 0:
                return False

            n_alive = len([m for m in battle.team.values() if not m.fainted])
            if active.current_hp_fraction < 0.30 and n_alive > 1:
                return False

            tera_type = self._get_tera_type(active)
            if tera_type is None:
                return False

            opp_types = [t for t in opp_active.types if t is not None]
            if not opp_types:
                return False

            offensive_tera_score = opp_active.damage_multiplier(move.type)

            def_scores = []
            for t in opp_types:
                mult = active.damage_multiplier(t)
                def_scores.append(1.0 / (mult if mult > 0 else 0.125))
            defensive_score = min(def_scores) if def_scores else 1.0

            def_tera_scores = []
            type_chart = getattr(active._data, "type_chart", None)
            for t in opp_types:
                if type_chart:
                    mult = t.damage_multiplier(tera_type, type_chart=type_chart)
                else:
                    mult = t.damage_multiplier(tera_type)
                def_tera_scores.append(1.0 / (mult if mult > 0 else 0.125))
            defensive_tera_score = min(def_tera_scores) if def_tera_scores else 1.0

            return offensive_tera_score * (defensive_tera_score / defensive_score) > 1.0
        except Exception:
            return False

    # -- Matchup Estimation (Move & Type Aware) --------------------------------

    def _estimate_max_damage(self, attacker, defender, gen: int, sets_db: dict) -> float:
        attacker_moves = list(attacker.moves.values()) if attacker.moves else []
        moves_data = GenData.from_gen(gen).moves

        if not attacker_moves:
            clean_name = attacker.species.lower().replace(" ", "").replace("-", "").replace("_", "")
            predicted = sets_db.get(clean_name, {}).get("moves", [])
            move_ids = predicted
        else:
            move_ids = [m.id for m in attacker_moves]

        atk = self._stat_estimation(attacker, "atk")
        df  = self._stat_estimation(defender, "def")
        spa = self._stat_estimation(attacker, "spa")
        sd  = self._stat_estimation(defender, "spd")

        if get_status_name(attacker) == "BRN":
            atk *= 0.5

        phys_ratio = atk / max(df, 1.0)
        spec_ratio = spa / max(sd, 1.0)

        max_dmg = 0.0

        if not move_ids:
            for t in attacker.types:
                if t is None:
                    continue
                eff = defender.damage_multiplier(t)
                ratio = phys_ratio if attacker.base_stats.get("atk", 100) >= attacker.base_stats.get("spa", 100) else spec_ratio
                dmg = 80.0 * ratio * eff * 1.5
                if dmg > max_dmg:
                    max_dmg = dmg
            return max_dmg

        for m_id in move_ids:
            m_data = moves_data.get(m_id)
            if not m_data:
                continue
            bp = m_data.get("basePower", 0)
            if bp <= 0:
                continue

            m_type_str = m_data.get("type", "").upper()
            if not m_type_str:
                continue

            try:
                m_type = PokemonType.from_name(m_type_str)
            except Exception:
                continue

            ability = getattr(defender, "ability", None)
            is_immune = False
            if ability:
                ability_str = str(ability).lower().replace(" ", "").replace("-", "")
                immune_type = ABILITY_IMMUNITIES.get(ability_str)
                if immune_type and m_type_str == immune_type:
                    is_immune = True
            if is_immune:
                continue

            eff = defender.damage_multiplier(m_type)
            if eff == 0.0:
                continue

            stab = 1.5 if m_type in attacker.types else 1.0
            category = m_data.get("category", "")
            ratio = phys_ratio if category == "Physical" else spec_ratio

            dmg = bp * ratio * eff * stab
            if dmg > max_dmg:
                max_dmg = dmg

        return max_dmg

    # -- Matchup Estimation (Move & Type Aware) --------------------------------

    def _estimate_matchup(self, mon, opponent, battle=None) -> float:
        gen = self._get_gen(battle)
        sets_db = self._load_pokemon_sets(gen)

        max_offensive = self._estimate_max_damage(mon, opponent, gen, sets_db)
        max_defensive = self._estimate_max_damage(opponent, mon, gen, sets_db)

        score = (max_offensive - max_defensive) / 200.0

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
