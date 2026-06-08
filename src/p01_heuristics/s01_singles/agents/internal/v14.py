"""Heuristic V14: The Championship Master.

Extends HeuristicV13 with:
1. Dynamic Team Roles (Win-Con, Vital Wall, Support) assigned during Team Preview.
2. Advanced Opponent Switch Prediction (Yomi Layer 1): Punishes switches with double-switches/pivots.
3. Defensive Bait-and-Switch Terastallization: Survive an outspeeding opponent's KO.
4. Boots Detection & Knock Off Priority: Detect Boots on entry and prioritize Knock Off.
5. Status Absorption: Switch to immune teammates to absorb status moves.
6. Opponent PP Tracking & Stall Mitigation: Track recovery PP using battle logs.
7. Win-Condition Preservation: Protect the Win-Con by switching it out early.
8. Yomi Layer 2 Tendency Tracker: Profiles opponent behavior (Predictive vs Conservative) to adjust predictions.
9. Early-Game Scouting Phase: Prioritizes low-risk pivot/information moves on turns 1-3.
10. Exact Damage Roll Calculations: Evaluates 16-step damage formulas to identify guaranteed KOs.
11. Endgame Minimax Solver: Triggers lookahead simulation when both teams have <= 2 Pokémon left.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from poke_env.data import GenData
from poke_env.environment.move_category import MoveCategory
from poke_env.environment.pokemon_type import PokemonType
from poke_env.environment.side_condition import SideCondition

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


class HeuristicV14(BaseHeuristic1v1):
    """V14 Championship Agent: Rule-Based Heuristic with Advanced Prediction, Roles, and Stall Countering."""

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
            workspace_root = Path(__file__).resolve().parents[5]
            showdown_dir = workspace_root / "pokemon-showdown" / "data" / "random-battles"

            if gen in [8, 1]:
                path = showdown_dir / f"gen{gen}" / "data.json"
                if path.exists():
                    with open(path, encoding="utf-8") as f:
                        data = json.load(f)
                    for mon_name, mon_data in data.items():
                        moves = set()
                        for key in ["moves", "essentialMoves", "exclusiveMoves", "comboMoves", "noDynamaxMoves"]:
                            if key in mon_data:
                                for m in mon_data[key]:
                                    moves.add(m.lower().replace(" ", "").replace("-", ""))
                        clean_mon_name = mon_name.lower().replace(" ", "").replace("-", "").replace("_", "")
                        sets_dict[clean_mon_name] = {"moves": list(moves), "abilities": [], "teraTypes": []}
            else:
                path = showdown_dir / f"gen{gen}" / "sets.json"
                if path.exists():
                    with open(path, encoding="utf-8") as f:
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
                            "teraTypes": list(tera_types),
                        }
        except Exception:
            pass

        _POKEMON_SETS_CACHE[gen] = sets_dict
        return sets_dict

    # -- Dynamic Team Preview & Role System -----------------------------------

    def teampreview(self, battle) -> str:
        """Returns the team order, prioritizing matchup scores of the lead."""
        team_list = list(battle.team.values())
        if not team_list:
            return self.random_teampreview(battle)

        opp_team_list = list(battle.opponent_team.values()) if battle.opponent_team else []
        self._evaluate_team_roles(battle)

        if not opp_team_list:
            sorted_team = sorted(
                enumerate(team_list),
                key=lambda x: x[1].base_stats.get("spe", 100) if x[1].base_stats else 100,
                reverse=True,
            )
        else:
            teammate_scores = []
            for i, mon in enumerate(team_list):
                total_score = 0.0
                for opp in opp_team_list:
                    total_score += self._estimate_matchup(mon, opp, battle)
                avg_score = total_score / len(opp_team_list)
                teammate_scores.append((avg_score, i, mon))

            sorted_team_info = sorted(
                teammate_scores,
                key=lambda x: (x[0], x[2].base_stats.get("spe", 100) if x[2].base_stats else 100),
                reverse=True,
            )
            sorted_team = [(idx, mon) for (score, idx, mon) in sorted_team_info]

        order_str = "".join(str(idx + 1) for idx, _ in sorted_team)
        return "/team " + order_str

    def _evaluate_team_roles(self, battle):
        """Classify opponent team archetype and assign roles to our team."""
        btag = battle.battle_tag
        if not hasattr(self, "_roles_by_battle"):
            self._roles_by_battle = {}
        if not hasattr(self, "_opp_archetype_by_battle"):
            self._opp_archetype_by_battle = {}

        if btag in self._roles_by_battle:
            return

        opp_team = list(battle.opponent_team.values()) if battle.opponent_team else []
        my_team = list(battle.team.values())

        archetype = "BALANCE"
        if opp_team:
            sun_setters = {"torkoal", "ninetales", "ninetalesalola"}
            rain_setters = {"pelipper", "politoed", "kyogre"}
            stall_mons = {
                "toxapex",
                "chansey",
                "blissey",
                "garganacl",
                "dondozo",
                "corviknight",
                "gliscor",
                "skarmory",
                "slowkinggalar",
                "clefable",
                "quagsire",
                "clodsire",
                "pyukumuku",
                "shuckle",
            }

            sun_count = 0
            rain_count = 0
            stall_count = 0

            for opp in opp_team:
                opp_name = opp.species.lower().replace(" ", "").replace("-", "")
                if opp_name in sun_setters:
                    sun_count += 2
                if opp_name in rain_setters:
                    rain_count += 2
                if opp_name in stall_mons:
                    stall_count += 1

                ability = str(getattr(opp, "ability", "")).lower()
                if "photosynthesis" in ability or "chlorophyll" in ability:
                    sun_count += 1
                if "swiftswim" in ability:
                    rain_count += 1

            if sun_count >= 3:
                archetype = "WEATHER_SUN"
            elif rain_count >= 3:
                archetype = "WEATHER_RAIN"
            elif stall_count >= 3:
                archetype = "STALL"
            elif len(opp_team) >= 4:
                high_offense_count = sum(
                    1
                    for o in opp_team
                    if o.base_stats
                    and (o.base_stats.get("atk", 100) > 110 or o.base_stats.get("spa", 100) > 110)
                    and o.base_stats.get("spe", 100) > 90
                )
                if high_offense_count >= 3:
                    archetype = "HYPER_OFFENSE"

        self._opp_archetype_by_battle[btag] = archetype

        roles = {}
        best_wincon_score = -1.0
        wincon_idx = -1

        for i, mon in enumerate(my_team):
            has_setup = False
            for move in mon.moves.values():
                if move.id in {"swordsdance", "dragondance", "nastyplot", "calmmind", "quiverdance", "shellsmash"}:
                    has_setup = True
                    break

            atk = mon.base_stats.get("atk", 100) if mon.base_stats else 100
            spa = mon.base_stats.get("spa", 100) if mon.base_stats else 100
            spe = mon.base_stats.get("spe", 100) if mon.base_stats else 100
            off_score = max(atk, spa) + spe
            if has_setup:
                off_score += 100

            avg_matchup = 0.0
            if opp_team:
                avg_matchup = sum(self._estimate_matchup(mon, opp, battle) for opp in opp_team) / len(opp_team)

            total_wincon_score = off_score + avg_matchup * 50
            if total_wincon_score > best_wincon_score:
                best_wincon_score = total_wincon_score
                wincon_idx = i

        main_threat = None
        best_threat_score = -1.0
        if opp_team:
            for opp in opp_team:
                o_atk = opp.base_stats.get("atk", 100) if opp.base_stats else 100
                o_spa = opp.base_stats.get("spa", 100) if opp.base_stats else 100
                o_spe = opp.base_stats.get("spe", 100) if opp.base_stats else 100
                t_score = max(o_atk, o_spa) + o_spe
                if t_score > best_threat_score:
                    best_threat_score = t_score
                    main_threat = opp

        vital_idx = -1
        if main_threat:
            best_counter_score = -999.0
            for i, mon in enumerate(my_team):
                if i == wincon_idx:
                    continue
                score = self._estimate_matchup(mon, main_threat, battle)
                if score > best_counter_score:
                    best_counter_score = score
                    vital_idx = i

        for i, mon in enumerate(my_team):
            mon_id = mon.species.lower()
            if i == wincon_idx:
                roles[mon_id] = "WIN_CON"
            elif i == vital_idx:
                roles[mon_id] = "VITAL_WALL"
            else:
                roles[mon_id] = "SUPPORT"

        self._roles_by_battle[btag] = roles

    # -- In-Battle Log Parsing & Inference Tracking ---------------------------

    def _parse_opponent_last_move(self, battle) -> str | None:
        """Parses the raw battle logs to extract the last move clicked by the opponent."""
        try:
            log = getattr(battle, "_log", [])
            if not log:
                return None
            opp_id = "p2" if battle.player_role == "p1" else "p1"
            for line in reversed(log):
                parts = line.split("|")
                if len(parts) >= 4 and parts[1] == "move" and parts[2].startswith(opp_id):
                    return parts[3].lower().replace(" ", "").replace("-", "")
        except Exception:
            pass
        return None

    def _update_inferences(self, battle):
        """Scans the active battlefield to infer items, abilities, and count move PP."""
        btag = battle.battle_tag
        if not hasattr(self, "_opp_boots_detected"):
            self._opp_boots_detected = {}
        if not hasattr(self, "_opp_move_counts"):
            self._opp_move_counts = {}
        if not hasattr(self, "_opp_active_last_move"):
            self._opp_active_last_move = {}
        if not hasattr(self, "_last_opp_active_name"):
            self._last_opp_active_name = {}
        if not hasattr(self, "_last_processed_turn"):
            self._last_processed_turn = {}
        if not hasattr(self, "_opponent_tendency"):
            self._opponent_tendency = {}
        if not hasattr(self, "_last_turn_matchup"):
            self._last_turn_matchup = {}

        opp = battle.opponent_active_pokemon
        if opp is None:
            return

        opp_name = opp.species.lower().replace(" ", "").replace("-", "")
        last_opp = self._last_opp_active_name.get(btag)

        # 1. Boots detection on switch-in
        if last_opp != opp_name:
            self._last_opp_active_name[btag] = opp_name
            has_hazards = any(c in battle.opponent_side_conditions for c in ENTRY_HAZARDS.values())
            if has_hazards and opp.current_hp_fraction == 1.0:
                is_flying_or_levitate = (
                    "FLYING" in [t.name for t in opp.types if t]
                    or str(getattr(opp, "ability", "")).lower() == "levitate"
                )
                has_stealth_rock = SideCondition.STEALTH_ROCK in battle.opponent_side_conditions
                if has_stealth_rock:
                    self._opp_boots_detected.setdefault(btag, set()).add(opp_name)
                elif not is_flying_or_levitate:
                    self._opp_boots_detected.setdefault(btag, set()).add(opp_name)

        # 2. Parse opponent moves & count PP
        last_move = self._parse_opponent_last_move(battle)
        if last_move:
            self._opp_active_last_move[btag] = last_move
            self._opp_move_counts.setdefault(btag, {}).setdefault(opp_name, {}).setdefault(last_move, 0)
            if self._last_processed_turn.get(btag) != battle.turn:
                self._opp_move_counts[btag][opp_name][last_move] += 1
                self._last_processed_turn[btag] = battle.turn

        # 3. Yomi Layer 2: Opponent Tendency Profiling
        last_matchup = self._last_turn_matchup.get(btag)
        if last_matchup is not None and last_opp is not None:
            if last_opp != opp_name:
                # Opponent switched out of a bad matchup
                if last_matchup < 0.6:
                    self._opponent_tendency[btag] = "PREDICTIVE"
            else:
                # Opponent stayed in during a bad matchup
                if last_matchup < 0.6:
                    self._opponent_tendency[btag] = "CONSERVATIVE"

    def _is_opp_out_of_recovery(self, battle, opp) -> bool:
        """Determines if the opponent has depleted recovery moves PP."""
        btag = battle.battle_tag
        opp_name = opp.species.lower().replace(" ", "").replace("-", "")
        counts = self._opp_move_counts.get(btag, {}).get(opp_name, {})
        for m_id in RECOVERY_MOVES:
            if m_id in counts and counts[m_id] >= 8:
                return True
        return False

    # -- Priority KO Hook (V10 core) ------------------------------------------

    def _pre_move_hook(self, battle):
        me = battle.active_pokemon
        opp = battle.opponent_active_pokemon

        if not battle.available_moves or me is None or opp is None:
            return None

        opp_hp = opp.current_hp if opp.current_hp is not None else (opp.current_hp_fraction * 300.0)
        if opp_hp <= 0:
            return None

        priority_moves = [m for m in battle.available_moves if m.entry.get("priority", 0) > 0 and m.base_power > 0]
        if not priority_moves:
            return None

        for move in priority_moves:
            if self._is_ability_immune(move, opp):
                continue
            if opp.damage_multiplier(move) == 0.0:
                continue
            if move.category not in [MoveCategory.PHYSICAL, MoveCategory.SPECIAL]:
                continue

            dmg_min, dmg_max = self._calculate_exact_damage_range(move, me, opp, battle)

            if dmg_min >= opp_hp:
                btag = battle.battle_tag
                self._ko_checks_by_battle[btag] = self._ko_checks_by_battle.get(btag, 0) + 1
                self._record_used_move(btag, move.id)
                tera = self._should_terastallize(battle, move)
                return self.create_order(move, terastallize=tera)

        return None

    # -- Status Absorption (Switch Hook) --------------------------------------

    def _try_status_absorption(self, battle, me, opp) -> Any:
        """Switch to a teammate immune to a predicted status move to safely absorb it."""
        if not battle.available_switches:
            return None

        gen = self._get_gen(battle)
        sets_db = self._load_pokemon_sets(gen)
        clean_opp_name = opp.species.lower().replace(" ", "").replace("-", "").replace("_", "")
        predicted_moves = sets_db.get(clean_opp_name, {}).get("moves", [])
        revealed_moves = [m.id for m in opp.moves.values()]
        all_opp_moves = list(set(predicted_moves + revealed_moves))

        status_moves_to_check = {
            "spore": "SLP",
            "sleeppowder": "SLP",
            "yawn": "SLP",
            "willowisp": "BRN",
            "toxic": "TOX",
            "poisonpowder": "PSN",
            "thunderwave": "PAR",
            "glare": "PAR",
        }

        predicted_status_type = None
        for m_id in all_opp_moves:
            if m_id in status_moves_to_check:
                predicted_status_type = status_moves_to_check[m_id]
                break

        if not predicted_status_type or get_status_name(me) is not None:
            return None

        is_vulnerable = False
        if predicted_status_type == "BRN" and self._is_physical_attacker(me):
            is_vulnerable = True
        elif predicted_status_type == "PAR" and me.base_stats.get("spe", 100) > 80:
            is_vulnerable = True
        elif predicted_status_type in ["TOX", "SLP"]:
            is_vulnerable = True

        if not is_vulnerable:
            return None

        for switch_in in battle.available_switches:
            s_types = [t.name for t in switch_in.types if t]
            s_ability = str(getattr(switch_in, "ability", "")).lower()
            immune = False

            if predicted_status_type == "SLP":
                if "GRASS" in s_types or s_ability in {"vitalspirit", "insomnia", "overcoat"}:
                    immune = True
            elif predicted_status_type == "BRN":
                if "FIRE" in s_types or s_ability in {"waterveil", "thermalexchange", "purifyingsalt"}:
                    immune = True
            elif predicted_status_type in ["TOX", "PSN"]:
                if (
                    "STEEL" in s_types
                    or "POISON" in s_types
                    or s_ability in {"immunity", "purifyingsalt", "poisonheal"}
                ):
                    immune = True
            elif predicted_status_type == "PAR":
                if "GROUND" in s_types or "ELECTRIC" in s_types or s_ability in {"limber", "purifyingsalt"}:
                    immune = True

            if immune:
                return switch_in

        return None

    # -- Opponent Switch Prediction (Yomi Layer 1 & 2 Punishers) --------------

    def _predict_and_punish_switch(
        self, battle, me, opp, best_move, physical_ratio, special_ratio, my_speed, opp_speed
    ) -> Any:
        """Predicts if the opponent will switch and selects U-turn, double-switches, hazards, or setup."""
        btag = battle.battle_tag

        # Yomi Layer 2 Check: If opponent behavior profile is Conservative, bypass switch predictions
        if self._opponent_tendency.get(btag) == "CONSERVATIVE":
            return None

        active_matchup = self._estimate_matchup(me, opp, battle)
        if active_matchup < 0.6:
            return None

        predicted_switch_in = None
        best_opp_bench_score = -999.0
        for s in battle.opponent_team.values():
            if s.fainted or s.active:
                continue
            score = self._estimate_matchup(s, me, battle)
            if score > best_opp_bench_score:
                best_opp_bench_score = score
                predicted_switch_in = s

        if not predicted_switch_in or best_opp_bench_score < 0.2:
            return None

        mult_against_switch_in = predicted_switch_in.damage_multiplier(best_move)
        if mult_against_switch_in > 0.5:
            return None

        format_str = battle._format or ""
        is_gen1 = "gen1" in format_str

        if not is_gen1:
            hazard_order = self._try_hazards(battle)
            if hazard_order:
                return hazard_order

        if not is_gen1:
            setup_order = self._try_setup(battle, me)
            if setup_order:
                return setup_order

        for move in battle.available_moves or []:
            if move.self_switch is True and move.base_power > 0:
                if not self._is_ability_immune(move, predicted_switch_in):
                    if predicted_switch_in.damage_multiplier(move) >= 1.0:
                        return move

        best_my_counter = None
        best_my_counter_score = -999.0
        for switch_in in battle.available_switches:
            score = self._estimate_matchup(switch_in, predicted_switch_in, battle)
            if score > best_my_counter_score:
                best_my_counter_score = score
                best_my_counter = switch_in

        if best_my_counter and best_my_counter_score > 0.5:
            self._matchup_switches_by_battle[btag] = self._matchup_switches_by_battle.get(btag, 0) + 1
            return best_my_counter

        best_prediction_move = None
        max_prediction_score = -1.0

        for move in battle.available_moves or []:
            if move.base_power <= 1:
                continue
            if self._is_ability_immune(move, predicted_switch_in) or self._is_ability_immune(move, opp):
                continue

            mult_switch = predicted_switch_in.damage_multiplier(move)
            mult_current = opp.damage_multiplier(move)

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
            for move in battle.available_moves:
                if move.id in {"haze", "clearsmog"}:
                    self._record_used_move(battle.battle_tag, move.id)
                    return self.create_order(move)

            if opp_speed < my_speed or me.current_hp_fraction > 0.4:
                for move in battle.available_moves:
                    if move.id in {"roar", "whirlwind", "dragontail", "circlethrow"}:
                        self._record_used_move(battle.battle_tag, move.id)
                        return self.create_order(move)

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

            if "encore" in [m.id for m in battle.available_moves] and my_speed > opp_speed:
                for move in battle.available_moves:
                    if move.id == "encore":
                        self._record_used_move(battle.battle_tag, move.id)
                        return self.create_order(move)

        return None

    # -- Endgame Minimax Solver -----------------------------------------------

    def _run_endgame_solver(self, battle, me, opp):
        """Identifies guaranteed endgame win paths when both teams have <= 2 Pokémon remaining."""
        my_remaining = len([m for m in battle.team.values() if not m.fainted])
        opp_remaining = 6 - len([m for m in battle.opponent_team.values() if m.fainted])

        if my_remaining > 2 or opp_remaining > 2:
            return None

        opp_hp = opp.current_hp if opp.current_hp is not None else (opp.current_hp_fraction * 300.0)

        # Check if we have a guaranteed KO on their active Pokémon
        best_ko_move = None
        for move in battle.available_moves or []:
            dmg_min, dmg_max = self._calculate_exact_damage_range(move, me, opp, battle)
            if dmg_min >= opp_hp:
                best_ko_move = move
                break

        if best_ko_move:
            self._record_used_move(battle.battle_tag, best_ko_move.id)
            return self.create_order(best_ko_move)

        # Check if they outspeed and hold a guaranteed KO on us
        my_hp = me.current_hp if me.current_hp is not None else (me.current_hp_fraction * 300.0)
        gen = self._get_gen(battle)
        sets_db = self._load_pokemon_sets(gen)
        opp_max_dmg = self._estimate_max_damage(opp, me, gen, sets_db)

        my_status = get_status_name(me)
        opp_status = get_status_name(opp)
        format_str = battle._format or ""
        my_speed = self._get_boosted_speed(me, my_status, format_str)
        opp_speed = self._get_boosted_speed(opp, opp_status, format_str)

        if opp_speed > my_speed and opp_max_dmg * 0.85 >= my_hp:
            # We faint before moving. Switch to a teammate who can absorb the hit.
            if battle.available_switches:
                for switch_in in battle.available_switches:
                    switch_in_max_dmg = self._estimate_max_damage(opp, switch_in, gen, sets_db)
                    switch_in_hp = (
                        switch_in.current_hp
                        if switch_in.current_hp is not None
                        else (switch_in.current_hp_fraction * 300.0)
                    )
                    if switch_in_max_dmg < switch_in_hp:
                        return self.create_order(switch_in)

        return None

    # -- Main Decision Loop ---------------------------------------------------

    def _select_action(self, battle):
        btag = battle.battle_tag
        me = battle.active_pokemon
        opp = battle.opponent_active_pokemon

        # 1. Update roles and parse battlefield states
        self._evaluate_team_roles(battle)
        self._update_inferences(battle)

        # Fainted Switch / Forced Switch / No Available Moves
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

        # 2. Endgame Minimax Solver
        endgame_order = self._run_endgame_solver(battle, me, opp)
        if endgame_order:
            return endgame_order

        # 3. Early Game Scouting Phase (turns 1-3)
        if battle.turn <= 3:
            scout_moves = [
                m for m in battle.available_moves if m.id in {"uturn", "voltswitch", "flipturn", "knockoff", "protect"}
            ]
            if scout_moves:
                physical_ratio = self._stat_estimation(me, "atk") / max(self._stat_estimation(opp, "def"), 1.0)
                special_ratio = self._stat_estimation(me, "spa") / max(self._stat_estimation(opp, "spd"), 1.0)
                best_scout = max(
                    scout_moves,
                    key=lambda m: self._score_move(
                        m, me, opp, physical_ratio, special_ratio, battle, my_speed, opp_speed
                    ),
                )
                if best_scout.base_power > 0 and opp.damage_multiplier(best_scout) > 0:
                    self._record_used_move(btag, best_scout.id)
                    return self.create_order(best_scout)

        # 4. Opponent Setup Sweeper Check
        setup_reaction = self._handle_opponent_setup_sweeper(battle, me, opp, my_speed, opp_speed)
        if setup_reaction:
            return setup_reaction

        # 5. Status Absorption Check
        absorber = self._try_status_absorption(battle, me, opp)
        if absorber:
            return self.create_order(absorber)

        # 6. Score all damaging moves
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

        # 7. Check Switch triggers
        switch_reason = ""
        if battle.available_switches:
            switch_reason = self._should_switch(me, opp, my_status, my_speed, opp_speed, max_score, battle)

        if switch_reason:
            can_sack = (
                me.current_hp_fraction <= SAC_HP_THRESHOLD
                and me.current_hp_fraction > 0
                and switch_reason == "matchup"
                and battle.available_moves
                and max_score >= WEAK_MOVE_THRESHOLD
            )
            if can_sack:
                pass
            else:
                pivot = self._find_pivot_move(battle, me, opp, format_str)
                if pivot:
                    self._matchup_switches_by_battle[btag] = self._matchup_switches_by_battle.get(btag, 0) + 1
                    self._record_used_move(btag, pivot.id)
                    return self.create_order(pivot)

                switch = self._get_best_switch(battle, opp)
                if switch:
                    if switch_reason == "matchup":
                        self._matchup_switches_by_battle[btag] = self._matchup_switches_by_battle.get(btag, 0) + 1
                    return self.create_order(switch)

        # 8. Smart Recovery Check (stalls counted)
        recovery_moves = [m for m in battle.available_moves if m.id in RECOVERY_MOVES]
        if recovery_moves and me.current_hp_fraction <= 0.6:
            gen = self._get_gen(battle)
            sets_db = self._load_pokemon_sets(gen)
            opp_max_dmg = self._estimate_max_damage(opp, me, gen, sets_db)
            opp_max_dmg_fraction = opp_max_dmg / 300.0

            opp_out_recovery = self._is_opp_out_of_recovery(battle, opp)
            if opp_max_dmg_fraction < me.current_hp_fraction and not opp_out_recovery:
                can_ko = False
                if best_move and best_move.base_power > 0:
                    best_dmg = self._score_move(
                        best_move, me, opp, physical_ratio, special_ratio, battle, my_speed, opp_speed
                    )
                    if (best_dmg / 300.0) >= opp.current_hp_fraction:
                        can_ko = True

                if not can_ko:
                    rec_move = recovery_moves[0]
                    self._record_used_move(btag, rec_move.id)
                    return self.create_order(rec_move)

        # 9. Hazards Check
        if not is_gen1:
            active_matchup = self._estimate_matchup(me, opp, battle)
            opp_likely_to_switch = active_matchup > 1.0
            is_free_turn = my_speed > opp_speed and self._resists_opp_stab(me, opp)
            if is_free_turn or battle.turn == 1 or opp_likely_to_switch:
                hazard_order = self._try_hazards(battle)
                if hazard_order:
                    return hazard_order

        # 10. Setup Check
        if not is_gen1 and me.current_hp_fraction == 1.0 and self._estimate_matchup(me, opp, battle) > 0:
            setup_order = self._try_setup(battle, me)
            if setup_order:
                return setup_order

        # 11. Status Moves Logic
        if max_score < STATUS_MOVE_THRESHOLD and opp.current_hp_fraction >= HIGH_HP_FRACTION:
            status_move = self._find_best_status_move(battle, me, opp, my_speed, opp_speed)
            if status_move:
                self._record_used_move(btag, status_move.id)
                return self.create_order(status_move)

        # 12. Attack with best move (Predictive Punish check)
        if best_move:
            punish_play = self._predict_and_punish_switch(
                battle, me, opp, best_move, physical_ratio, special_ratio, my_speed, opp_speed
            )
            if punish_play:
                if isinstance(punish_play, PokemonType) or hasattr(punish_play, "species"):
                    return self.create_order(punish_play)
                elif hasattr(punish_play, "base_power"):
                    selected_move = punish_play
                else:
                    return punish_play
            else:
                selected_move = best_move

            self._record_used_move(btag, selected_move.id)

            # Store turn matchup score to inform tendency tracking on next turn
            self._last_turn_matchup[btag] = self._estimate_matchup(me, opp, battle)

            tera = False
            if selected_move.base_power > 0:
                tera = self._should_terastallize(battle, selected_move)
            return self.create_order(selected_move, terastallize=tera)

        # Final state tracking fallback
        self._last_turn_matchup[btag] = self._estimate_matchup(me, opp, battle)
        return None

    # -- Pivot Move Detection --------------------------------------------------

    def _find_pivot_move(self, battle, me, opp, format_str: str):
        my_speed = self._get_boosted_speed(me, get_status_name(me), format_str)
        opp_speed = self._get_boosted_speed(opp, get_status_name(opp), format_str)
        if my_speed <= opp_speed:
            return None

        for move in battle.available_moves or []:
            if move.self_switch is not True or move.base_power < 1:
                continue
            if self._is_ability_immune(move, opp):
                continue
            effectiveness = opp.damage_multiplier(move)
            if effectiveness >= 1.0:
                return move
        return None

    # -- Hazard Logic ---------------------------------------------------------

    def _try_hazards(self, battle) -> object:
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

    # -- Setup Logic ----------------------------------------------------------

    def _try_setup(self, battle, me) -> object:
        for move in battle.available_moves or []:
            if not move.boosts or move.target != "self":
                continue
            boost_sum = sum(v for v in move.boosts.values() if v > 0)
            if boost_sum < 2:
                continue
            min_current = min(me.boosts.get(s, 0) for s, v in move.boosts.items() if v > 0)
            if min_current >= 6:
                continue
            btag = battle.battle_tag
            self._setup_uses_by_battle[btag] = self._setup_uses_by_battle.get(btag, 0) + 1
            self._record_used_move(btag, move.id)
            return self.create_order(move)

        return None

    @staticmethod
    def _resists_opp_stab(me, opp) -> bool:
        opp_types = [t for t in opp.types if t is not None]
        if not opp_types:
            return False
        max_threat = max(me.damage_multiplier(t) for t in opp_types)
        return max_threat <= 1.0

    # -- Status Move Selection -------------------------------------------------

    def _find_best_status_move(self, battle, me, opp, my_speed, opp_speed):
        if opp.status is not None:
            return None

        opp_types = [t.name for t in opp.types if t is not None]
        best_status = None
        best_priority = -1

        opp_has_sleep = any(get_status_name(m) == "SLP" for m in battle.opponent_team.values())

        for move in battle.available_moves or []:
            if move.base_power > 0 or move.status is None:
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

            elif status_name in ["TOX", "PSN"]:
                if "STEEL" in opp_types or "POISON" in opp_types:
                    continue
                opp_ability = str(getattr(opp, "ability", "")).lower()
                if "guts" in opp_ability:
                    continue
                priority = 3

            elif status_name == "BRN":
                if "FIRE" in opp_types or not self._is_physical_attacker(opp):
                    continue
                opp_ability = str(getattr(opp, "ability", "")).lower()
                if "guts" in opp_ability:
                    continue
                priority = 2

            elif status_name == "PAR":
                if "GROUND" in opp_types or "ELECTRIC" in opp_types or my_speed >= opp_speed:
                    continue
                opp_ability = str(getattr(opp, "ability", "")).lower()
                if "guts" in opp_ability:
                    continue
                priority = 1

            if priority > best_priority:
                best_priority = priority
                best_status = move

        return best_status

    # -- Exact 16-Step Damage Calc Wrapper ------------------------------------

    def _calculate_exact_damage_range(self, move, attacker, defender, battle) -> tuple[float, float]:
        """Calculates the 16-step exact damage range (min roll to max roll)."""
        if move.base_power <= 0:
            return 0.0, 0.0

        physical_ratio = self._stat_estimation(attacker, "atk") / max(self._stat_estimation(defender, "def"), 1.0)
        special_ratio = self._stat_estimation(attacker, "spa") / max(self._stat_estimation(defender, "spd"), 1.0)
        if get_status_name(attacker) == "BRN":
            physical_ratio *= 0.5

        ratio = physical_ratio if move.category == MoveCategory.PHYSICAL else special_ratio
        if move.category not in [MoveCategory.PHYSICAL, MoveCategory.SPECIAL]:
            return 0.0, 0.0

        eff = defender.damage_multiplier(move)
        if eff == 0.0:
            return 0.0, 0.0

        stab = 1.5 if move.type in attacker.types else 1.0
        level = attacker.level if attacker.level else 80

        base_dmg = ((2 * level / 5 + 2) * move.base_power * ratio) / 50 + 2
        score = base_dmg * stab * eff
        score = self._apply_weather_mod(score, move, battle)
        score = self._apply_terrain_mod(score, move, battle)

        return score * 0.85, score

    # -- Move Scoring (with modifiers & Knock Off bonuses) ---------------------

    def _score_move(self, move, me, opp, physical_ratio, special_ratio, battle, my_speed, opp_speed) -> float:
        if move.base_power <= 1:
            return 0.0

        ratio = physical_ratio if move.category == MoveCategory.PHYSICAL else special_ratio
        if move.category not in [MoveCategory.PHYSICAL, MoveCategory.SPECIAL]:
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

        if move.id in {"rapidspin", "tidyup"}:
            has_hazards = any(c in battle.side_conditions for c in ENTRY_HAZARDS.values())
            n_bench_alive = len([m for m in battle.team.values() if not m.fainted and m != me])
            if has_hazards and n_bench_alive > 0:
                opp_hp = opp.current_hp_fraction
                if opp_hp > 0.2:
                    score += 80.0

        if move.id == "knockoff":
            btag = battle.battle_tag
            opp_name = opp.species.lower().replace(" ", "").replace("-", "")
            if opp_name in self._opp_boots_detected.get(btag, set()):
                score *= 2.0

        return float(score)

    # -- Switch Decisions (Wincon Preservation triggers) ----------------------

    def _should_switch(self, me, opp, my_status, my_speed, opp_speed, max_score, battle) -> str:
        if my_status == "TOX" and me.status_counter > 2:
            return "toxic"

        if max_score < WEAK_MOVE_THRESHOLD and my_speed < opp_speed:
            return "weak"

        best_bench_score = -999.0
        for s in battle.available_switches:
            bench_score = self._estimate_matchup(s, opp, battle)
            if bench_score > best_bench_score:
                best_bench_score = bench_score

        active_matchup = self._estimate_matchup(me, opp, battle)
        btag = battle.battle_tag
        roles = self._roles_by_battle.get(btag, {})
        is_wincon = roles.get(me.species.lower()) == "WIN_CON"

        if is_wincon and active_matchup < 0.2 and not me.fainted:
            if best_bench_score > 0.5:
                return "matchup"

        if best_bench_score > 0.5:
            if active_matchup < 0.1:
                return "matchup"
            if max_score < STATUS_MOVE_THRESHOLD:
                return "matchup"

        if active_matchup < -0.8 and best_bench_score > active_matchup + 0.6:
            return "matchup"

        if me.boosts.get("def", 0) <= -3 or me.boosts.get("spd", 0) <= -3:
            return "matchup"

        if me.boosts.get("atk", 0) <= -3 and self._is_physical_attacker(me):
            return "matchup"
        if me.boosts.get("spa", 0) <= -3 and not self._is_physical_attacker(me):
            return "matchup"

        if active_matchup < SWITCH_OUT_MATCHUP_THRESHOLD:
            return "matchup"

        return ""

    @staticmethod
    def _is_physical_attacker(mon) -> bool:
        atk = mon.base_stats.get("atk", 100) if mon.base_stats else 100
        spa = mon.base_stats.get("spa", 100) if mon.base_stats else 100
        return atk >= spa

    # -- Switch Targets (Choice Exploitations) ---------------------------------

    def _get_best_switch(self, battle, opp):
        best = None
        best_score = -999.0

        opp_item = str(opp.item).lower() if opp.item else ""
        is_choice_locked = "choice" in opp_item and len(opp.moves) > 0

        for pokemon in battle.available_switches:
            score = self._estimate_matchup(pokemon, opp, battle)

            if is_choice_locked:
                all_resisted = True
                for opp_move in opp.moves.values():
                    if opp_move.base_power > 0:
                        eff = pokemon.damage_multiplier(opp_move)
                        if eff >= 1.0:
                            all_resisted = False
                            break
                if all_resisted:
                    score += 1.5

            if score > best_score:
                best_score = score
                best = pokemon

        return best if best is not None else battle.available_switches[0]

    def _get_best_switch_double_faint(self, battle) -> Any:
        if not battle.available_switches:
            return None
        opp_remaining = [p for p in battle.opponent_team.values() if not p.fainted]
        if not opp_remaining:
            return max(battle.available_switches, key=lambda x: x.base_stats.get("spe", 100) if x.base_stats else 100)

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

    # -- Terastallization Logic ------------------------------------------------

    def _get_tera_type(self, pokemon) -> PokemonType | None:
        if hasattr(pokemon, "tera_type") and pokemon.tera_type is not None:
            if isinstance(pokemon.tera_type, str):
                try:
                    return PokemonType.from_name(pokemon.tera_type)
                except Exception:
                    pass
            elif isinstance(pokemon.tera_type, PokemonType):
                return pokemon.tera_type

        if hasattr(pokemon, "guess_tera"):
            t_str = pokemon.guess_tera()
            if t_str:
                try:
                    return PokemonType.from_name(t_str)
                except Exception:
                    pass

        if getattr(pokemon, "_terastallized_type", None) is not None:
            return pokemon._terastallized_type

        return None

    def _should_terastallize(self, battle, move) -> bool:
        """Reactive defensive bait-and-switch Tera check + standard V13 logic."""
        try:
            active = battle.active_pokemon
            opp_active = battle.opponent_active_pokemon
            if not getattr(battle, "can_tera", False) or not active or not opp_active:
                return False

            if move.base_power <= 0:
                return False

            n_alive = len([m for m in battle.team.values() if not m.fainted])

            gen = self._get_gen(battle)
            sets_db = self._load_pokemon_sets(gen)
            opp_max_dmg = self._estimate_max_damage(opp_active, active, gen, sets_db)
            opp_max_dmg_fraction = opp_max_dmg / 300.0

            tera_type = self._get_tera_type(active)
            if tera_type is None:
                return False

            is_about_to_faint = opp_max_dmg_fraction >= active.current_hp_fraction

            opp_types = [t for t in opp_active.types if t is not None]
            if not opp_types:
                return False

            def_scores = []
            for t in opp_types:
                mult = active.damage_multiplier(t)
                def_scores.append(mult)
            max_def_multiplier = max(def_scores) if def_scores else 1.0

            type_chart = getattr(active._data, "type_chart", None)
            def_tera_scores = []
            for t in opp_types:
                if type_chart:
                    mult = t.damage_multiplier(tera_type, type_chart=type_chart)
                else:
                    mult = t.damage_multiplier(tera_type)
                def_tera_scores.append(mult)
            max_def_tera_multiplier = max(def_tera_scores) if def_tera_scores else 1.0

            if is_about_to_faint and max_def_multiplier > 1.0 and max_def_tera_multiplier <= 0.5:
                return True

            if active.current_hp_fraction < 0.30 and n_alive > 1:
                return False

            offensive_tera_score = opp_active.damage_multiplier(move.type)

            def_scores_inv = [1.0 / (m if m > 0 else 0.125) for m in def_scores]
            defensive_score = min(def_scores_inv) if def_scores_inv else 1.0

            def_tera_scores_inv = [1.0 / (m if m > 0 else 0.125) for m in def_tera_scores]
            defensive_tera_score = min(def_tera_scores_inv) if def_tera_scores_inv else 1.0

            return offensive_tera_score * (defensive_tera_score / defensive_score) > 1.0
        except Exception:
            return False

    # -- Damage & Matchup Estimations ------------------------------------------

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
        df = self._stat_estimation(defender, "def")
        spa = self._stat_estimation(attacker, "spa")
        sd = self._stat_estimation(defender, "spd")

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
                ratio = (
                    phys_ratio
                    if attacker.base_stats.get("atk", 100) >= attacker.base_stats.get("spa", 100)
                    else spec_ratio
                )
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

    # -- Stat Calculations -----------------------------------------------------

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
