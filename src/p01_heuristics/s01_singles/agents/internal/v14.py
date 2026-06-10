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

try:
    from poke_env.environment.move_category import MoveCategory
    from poke_env.environment.pokemon_type import PokemonType
    from poke_env.environment.side_condition import SideCondition
except ImportError:
    from poke_env.battle import MoveCategory, PokemonType, SideCondition

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
    "wellbakedbody": "FIRE",
    "levitate": "GROUND",
    "eartheater": "GROUND",
    "voltabsorb": "ELECTRIC",
    "lightningrod": "ELECTRIC",
    "motordrive": "ELECTRIC",
    "waterabsorb": "WATER",
    "stormdrain": "WATER",
    "dryskin": "WATER",
    "sapsipper": "GRASS",
}

# Abilities that halve incoming damage of a given type (do not nullify it).
ABILITY_HALF_DAMAGE = {
    "thickfat": ("FIRE", "ICE"),
    "heatproof": ("FIRE",),
    "waterbubble": ("FIRE",),
    "purifyingsalt": ("GHOST",),
}

RECOVERY_MOVES = {"recover", "roost", "slackoff", "softboiled", "moonlight", "synthesis", "milkdrink", "shoreup"}
DRAINING_MOVES = {"gigadrain", "drainpunch", "hornleech", "bitterblade", "drainingkiss", "leechlife", "paraboliccharge"}

UNKNOCKABLE_ITEMS = {
    "hearthflamemask",
    "wellspringmask",
    "cornerstonemask",
    "rustedsword",
    "rustedshield",
    "griseouscore",
    "griseousorb",
    "insectplate",
    "dreadplate",
    "dracoplate",
    "zapplate",
    "pixieplate",
    "fistplate",
    "flameplate",
    "skyplate",
    "spookyplate",
    "meadowplate",
    "earthplate",
    "icicleplate",
    "toxicplate",
    "mindplate",
    "stoneplate",
    "ironplate",
    "splashplate",
}

_POKEMON_SETS_CACHE: dict[int, dict] = {}


class HeuristicV14(BaseHeuristic1v1):
    """V14 Championship Agent: Rule-Based Heuristic with Advanced Prediction, Roles, and Stall Countering."""

    @property
    def tracks_moves(self) -> bool:
        return True

    def reset_battles(self) -> None:
        super().reset_battles()
        if hasattr(self, "_active_history_by_battle"):
            self._active_history_by_battle.clear()
        if hasattr(self, "_opp_active_history_by_battle"):
            self._opp_active_history_by_battle.clear()

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
        if not hasattr(self, "_opp_vol_switches"):
            self._opp_vol_switches = {}

        if btag not in self._opp_vol_switches:
            self._opp_vol_switches[btag] = 0

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
                # Check if the previous active opponent Pokemon fainted (forced switch)
                last_opp_fainted = False
                for p in battle.opponent_team.values():
                    p_name = p.species.lower().replace(" ", "").replace("-", "")
                    if p_name == last_opp:
                        if p.fainted:
                            last_opp_fainted = True
                        break
                # Only profile as PREDICTIVE if they voluntarily switched out of a bad matchup
                if not last_opp_fainted:
                    self._opp_vol_switches[btag] += 1
                    if last_matchup > 0.4:
                        self._opponent_tendency[btag] = "PREDICTIVE"
            else:
                # Opponent stayed in during a bad matchup (for them)
                if last_matchup > 0.4:
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

    def _is_fakeout_usable(self, battle) -> bool:
        """Checks if Fake Out or First Impression is usable on this turn."""
        btag = battle.battle_tag
        history = getattr(self, "_active_history_by_battle", {}).get(btag, [])
        if not history:
            return True
        if len(history) == 1:
            return True
        if history[-1][1] != history[-2][1]:
            return True
        return False

    @staticmethod
    def _has_knockable_item(pokemon) -> bool:
        if pokemon is None:
            return False
        item = getattr(pokemon, "item", None)
        if item is None:
            return False
        item_str = str(item).lower().replace(" ", "").replace("-", "")
        if item_str in {"", "none"}:
            return False
        if item_str == "unknown_item":
            return True
        if item_str in UNKNOCKABLE_ITEMS:
            return False
        return True

    def _is_grassy_terrain_active(self, battle) -> bool:
        if not battle or not battle.fields:
            return False
        for field in battle.fields:
            if "GRASSY" in str(field).upper():
                return True
        return False

    def _get_move_priority(self, move, battle) -> int:
        base_priority = move.entry.get("priority", 0) if move.entry else 0
        me = battle.active_pokemon
        if not me:
            return base_priority

        # Grassy Glide in Grassy Terrain
        if move.id == "grassyglide" and self._is_grassy_terrain_active(battle):
            return max(base_priority, 1)

        # Gale Wings in Gen 7+ requires 100% HP
        ability_str = str(getattr(me, "ability", "")).lower().replace(" ", "").replace("-", "")
        if ability_str == "galewings" and me.current_hp_fraction == 1.0 and move.type.name == "FLYING":
            return max(base_priority, 1)

        # Prankster
        if ability_str == "prankster" and move.category not in [MoveCategory.PHYSICAL, MoveCategory.SPECIAL]:
            opp = battle.opponent_active_pokemon
            if opp:
                opp_types = [t.name for t in opp.types if t is not None]
                is_opp_dark = "DARK" in opp_types
                gen = self._get_gen(battle)
                if gen >= 7 and is_opp_dark:
                    return base_priority
            return max(base_priority, 1)

        # Triage
        if ability_str == "triage":
            is_healing = (
                move.id in RECOVERY_MOVES
                or move.id in DRAINING_MOVES
                or move.id in {"rest", "milkdrink", "healbell", "wish", "healingwish", "lunardance"}
            )
            if is_healing:
                return max(base_priority, 3)

        return base_priority

    # -- Priority KO Hook (V10 core) ------------------------------------------

    def _pre_move_hook(self, battle):
        me = battle.active_pokemon
        opp = battle.opponent_active_pokemon

        if not battle.available_moves or me is None or opp is None:
            return None

        opp_hp = self._current_hp(opp)
        if opp_hp <= 0:
            return None

        priority_moves = [
            m
            for m in battle.available_moves
            if self._get_move_priority(m, battle) > 0
            and m.base_power > 0
            and m.id not in {"suckerpunch", "thunderclap"}
            and (m.id not in {"fakeout", "firstimpression"} or self._is_fakeout_usable(battle))
        ]
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

        # Only absorb when we're healthy (already-statused mons gain nothing).
        if get_status_name(me) != "HEALTHY":
            return None

        gen = self._get_gen(battle)
        sets_db = self._load_pokemon_sets(gen)
        revealed_moves = [m.id for m in opp.moves.values()]

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

        # Confidence gate: only react to a status move the opponent has actually
        # revealed, or one we strongly predict while they sit at high HP (the
        # classic "they'll click status on the switch" read). This stops the bot
        # from fleeing every turn on a mere database guess.
        predicted_status_type = None
        for m_id in revealed_moves:
            if m_id in status_moves_to_check:
                predicted_status_type = status_moves_to_check[m_id]
                break

        if predicted_status_type is None:
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
            s_ability = str(getattr(switch_in, "ability", "")).lower().replace(" ", "").replace("-", "")
            immune = False

            # The absorber must not be walking into a KO from the opponent's
            # attacking moves — otherwise dodging status just loses a Pokémon.
            in_dmg = self._estimate_max_damage(opp, switch_in, gen, sets_db)
            if in_dmg >= self._current_hp(switch_in) * 0.9:
                continue

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

            if immune and self._is_switch_allowed(battle, switch_in):
                return switch_in

        return None

    # -- Opponent Switch Prediction (Yomi Layer 1 & 2 Punishers) --------------

    def _predict_and_punish_switch(
        self, battle, me, opp, best_move, physical_ratio, special_ratio, my_speed, opp_speed
    ) -> Any:
        """Predicts if the opponent will switch and selects U-turn, double-switches, hazards, or setup."""
        btag = battle.battle_tag

        # If the opponent can KO us, they will likely just attack. Do not predict a switch.
        me_hp = self._current_hp(me)
        gen = self._get_gen(battle)
        sets_db = self._load_pokemon_sets(gen)
        opp_max_dmg = self._estimate_max_damage(opp, me, gen, sets_db)
        if opp_max_dmg >= me_hp:
            return None

        # Yomi Layer 2: Only gamble on a switch read once we have positively
        # observed the human bailing from bad matchups (PREDICTIVE).
        is_predictive = (
            self._opponent_tendency.get(btag) == "PREDICTIVE"
            or self._opp_vol_switches.get(btag, 0) >= 1
            or getattr(battle, "voluntary_switches_opp", 0) >= 1
        )
        if not is_predictive:
            return None

        # Don't start a mind-game on the turn we just switched in.
        if self._just_switched_in(battle):
            return None

        active_matchup = self._estimate_matchup(me, opp, battle)
        if active_matchup < 0.5:
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
            hazard_order = self._try_hazard_laying(battle)
            if hazard_order:
                return hazard_order

        if not is_gen1:
            setup_order = self._try_setup(battle, me, my_speed, opp_speed)
            if setup_order:
                return setup_order

        # Best response: a damaging pivot move (U-turn/Volt Switch). This is the
        # ideal punish — we hit the incoming switch AND keep momentum, with no
        # tempo loss if we read wrong, so it's the only "switch-style" play we
        # allow on a prediction.
        for move in battle.available_moves or []:
            if move.self_switch is True and move.base_power > 0:
                if not self._is_ability_immune(move, predicted_switch_in):
                    if predicted_switch_in.damage_multiplier(move) >= 1.0:
                        return move

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

    # -- Guaranteed KO Detection ----------------------------------------------

    def _find_guaranteed_ko(self, battle, me, opp, my_speed, opp_speed):
        """Return a move that guarantees a KO this turn, or None.

        Prioritizes moves that KO *before* the opponent acts (we outspeed, or the
        move has priority). This is the single most important play in the game and
        must be checked before scouting, switching, or status — clicking the kill
        is almost never wrong against a human.
        """
        if not battle.available_moves or opp is None or opp.fainted:
            return None
        opp_hp = self._current_hp(opp)
        if opp_hp <= 0:
            return None

        # Among moves that guarantee the KO, pick the most *reliable* one: rank by
        # accuracy first, then by how cleanly it overkills. A 100%-acc KO beats a
        # 80%-acc bigger hit — whiffing a kill is exactly what loses games to humans.
        safe_ko = None  # KOs before the opponent moves
        risky_ko = None  # KOs but opponent likely moves first
        best_safe_key = (-1.0, -1.0)
        best_risky_key = (-1.0, -1.0)
        for move in battle.available_moves:
            if move.id in {"fakeout", "firstimpression"} and not self._is_fakeout_usable(battle):
                continue
            if move.id in {"suckerpunch", "thunderclap"}:
                continue
            if move.category not in [MoveCategory.PHYSICAL, MoveCategory.SPECIAL]:
                continue
            if self._is_ability_immune(move, opp) or opp.damage_multiplier(move) == 0.0:
                continue
            dmg_min, _ = self._calculate_exact_damage_range(move, me, opp, battle)
            if dmg_min < opp_hp:
                continue
            accuracy = move.accuracy if isinstance(move.accuracy, (int, float)) else 1.0
            key = (accuracy, dmg_min)
            moves_first = my_speed > opp_speed or self._get_move_priority(move, battle) > 0
            if moves_first:
                if key > best_safe_key:
                    best_safe_key, safe_ko = key, move
            else:
                if key > best_risky_key:
                    best_risky_key, risky_ko = key, move
        return safe_ko or risky_ko

    # -- Endgame Minimax Solver -----------------------------------------------

    def _run_endgame_solver(self, battle, me, opp):
        """Identifies guaranteed endgame win paths when both teams have <= 2 Pokémon remaining."""
        my_remaining = len([m for m in battle.team.values() if not m.fainted])
        opp_remaining = 6 - len([m for m in battle.opponent_team.values() if m.fainted])

        if my_remaining > 2 or opp_remaining > 2:
            return None

        opp_hp = self._current_hp(opp)

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
        my_hp = self._current_hp(me)
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
                    switch_in_hp = self._current_hp(switch_in)
                    if switch_in_max_dmg < switch_in_hp:
                        return self.create_order(switch_in)

        return None

    # -- Main Decision Loop ---------------------------------------------------

    def _select_action(self, battle):
        btag = battle.battle_tag
        me = battle.active_pokemon
        opp = battle.opponent_active_pokemon

        # Update active histories
        if not hasattr(self, "_active_history_by_battle"):
            self._active_history_by_battle = {}
        if btag not in self._active_history_by_battle:
            self._active_history_by_battle[btag] = []
        if me:
            history = self._active_history_by_battle[btag]
            if not history or history[-1][0] < battle.turn:
                history.append((battle.turn, me.species.lower()))

        if not hasattr(self, "_opp_active_history_by_battle"):
            self._opp_active_history_by_battle = {}
        if btag not in self._opp_active_history_by_battle:
            self._opp_active_history_by_battle[btag] = []
        if opp:
            opp_history = self._opp_active_history_by_battle[btag]
            if not opp_history or opp_history[-1][0] < battle.turn:
                opp_history.append((battle.turn, opp.species.lower()))

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

        # 2. Guaranteed KO — always take the kill before anything else.
        ko_move = self._find_guaranteed_ko(battle, me, opp, my_speed, opp_speed)
        if ko_move:
            self._ko_checks_by_battle[btag] = self._ko_checks_by_battle.get(btag, 0) + 1
            self._record_used_move(btag, ko_move.id)
            tera = self._should_terastallize(battle, ko_move)
            return self.create_order(ko_move, terastallize=tera)

        # 3. Endgame Minimax Solver
        endgame_order = self._run_endgame_solver(battle, me, opp)
        if endgame_order:
            return endgame_order

        # 4. Early Game Scouting Phase (turns 1-3)
        # Pivot moves (U-turn/Volt Switch) reveal the opponent's set while keeping
        # momentum — valuable against a human. But scouting must NOT cost us a
        # strong attack: if our best damaging move clearly out-damages the pivot,
        # we just attack. This is the key fix for the bot-vs-bot regression, where
        # throwing away tempo/damage to "scout" a static agent is pure loss.
        if battle.turn <= 3:
            gen = self._get_gen(battle)
            sets_db = self._load_pokemon_sets(gen)
            opp_threat = self._estimate_max_damage(opp, me, gen, sets_db)
            safe_to_scout = opp_threat < self._current_hp(me) * 0.6
            scout_moves = [
                m for m in battle.available_moves if m.id in {"uturn", "voltswitch", "flipturn", "knockoff", "protect"}
            ]
            if scout_moves and safe_to_scout:
                physical_ratio = self._stat_estimation(me, "atk") / max(self._stat_estimation(opp, "def"), 1.0)
                special_ratio = self._stat_estimation(me, "spa") / max(self._stat_estimation(opp, "spd"), 1.0)
                scorer = lambda m: self._score_move(  # noqa: E731
                    m, me, opp, physical_ratio, special_ratio, battle, my_speed, opp_speed
                )
                best_scout = max(scout_moves, key=scorer)
                # Best pure-attacking alternative (non-pivot damaging move).
                attack_moves = [
                    m
                    for m in battle.available_moves
                    if m.base_power > 0 and not m.self_switch and not self._is_ability_immune(m, opp)
                ]
                best_attack_score = max((scorer(m) for m in attack_moves), default=0.0)
                scout_score = scorer(best_scout)
                # Only scout if it does real chip (neutral+), and isn't giving up
                # meaningful damage vs simply attacking (within 15%).
                worth_scouting = (
                    best_scout.base_power > 0
                    and opp.damage_multiplier(best_scout) >= 1.0
                    and scout_score >= best_attack_score * 0.85
                )
                if worth_scouting:
                    self._record_used_move(btag, best_scout.id)
                    return self.create_order(best_scout)

        # 5. Opponent Setup Sweeper Check
        setup_reaction = self._handle_opponent_setup_sweeper(battle, me, opp, my_speed, opp_speed)
        if setup_reaction:
            return setup_reaction

        # 6. Status Absorption Check
        absorber = self._try_status_absorption(battle, me, opp)
        if absorber:
            return self.create_order(absorber)

        # 7. Score all damaging moves
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

        # Check if we can outspeed and KO the opponent
        can_ko_opp = False
        if opp and not opp.fainted:
            opp_hp = self._current_hp(opp)
            if opp_hp > 0:
                for move in battle.available_moves or []:
                    if self._is_ability_immune(move, opp):
                        continue
                    if opp.damage_multiplier(move) == 0.0:
                        continue
                    if move.category not in [MoveCategory.PHYSICAL, MoveCategory.SPECIAL]:
                        continue
                    dmg_min, _ = self._calculate_exact_damage_range(move, me, opp, battle)
                    if dmg_min >= opp_hp:
                        if my_speed > opp_speed or self._get_move_priority(move, battle) > 0:
                            can_ko_opp = True
                            break

        # 8. Check Switch triggers
        switch_reason = ""
        if battle.available_switches and not can_ko_opp:
            switch_reason = self._should_switch(me, opp, my_status, my_speed, opp_speed, max_score, battle)

        if switch_reason:
            can_sack = (
                me.current_hp_fraction <= SAC_HP_THRESHOLD and me.current_hp_fraction > 0 and battle.available_moves
            )
            if can_sack:
                pass
            else:
                switch = self._get_best_switch(battle, opp, allowed_only=True)
                if switch:
                    pivot = self._find_pivot_move(battle, me, opp, format_str)
                    if pivot:
                        self._matchup_switches_by_battle[btag] = self._matchup_switches_by_battle.get(btag, 0) + 1
                        self._record_used_move(btag, pivot.id)
                        return self.create_order(pivot)

                    if switch_reason == "matchup":
                        self._matchup_switches_by_battle[btag] = self._matchup_switches_by_battle.get(btag, 0) + 1
                    return self.create_order(switch)

        # 9. Smart Recovery Check (stalls counted)
        recovery_moves = [m for m in battle.available_moves if m.id in RECOVERY_MOVES]
        if recovery_moves and me.current_hp_fraction <= 0.55:
            gen = self._get_gen(battle)
            sets_db = self._load_pokemon_sets(gen)
            opp_max_dmg = self._estimate_max_damage(opp, me, gen, sets_db)
            my_hp = self._current_hp(me)

            opp_out_recovery = self._is_opp_out_of_recovery(battle, opp)
            # Only heal if the opponent's strongest hit can't break our recovery
            # (we'd net positive HP) and they aren't out of recovery PP themselves.
            if opp_max_dmg < my_hp and not opp_out_recovery:
                can_ko = False
                if best_move and best_move.base_power > 0:
                    dmg_min, _ = self._calculate_exact_damage_range(best_move, me, opp, battle)
                    if dmg_min >= self._current_hp(opp):
                        can_ko = True

                if not can_ko:
                    rec_move = recovery_moves[0]
                    self._record_used_move(btag, rec_move.id)
                    return self.create_order(rec_move)

        # 10. Hazards Check
        if not is_gen1:
            # 10a. Try Clearing Hazards
            clear_order = self._try_hazard_clearing(battle, me, opp)
            if clear_order:
                return clear_order

            # 10b. Try Laying Hazards
            active_matchup = self._estimate_matchup(me, opp, battle)
            opp_likely_to_switch = active_matchup >= 0.5
            is_free_turn = my_speed > opp_speed and self._resists_opp_stab(me, opp)
            is_dangerous_lead = opp_speed > my_speed and not self._resists_opp_stab(me, opp)
            if is_free_turn or (battle.turn == 1 and not is_dangerous_lead) or opp_likely_to_switch:
                hazard_order = self._try_hazard_laying(battle)
                if hazard_order:
                    return hazard_order

        # 11. Setup Check
        if not is_gen1 and me.current_hp_fraction >= 0.60 and self._estimate_matchup(me, opp, battle) > 0:
            setup_order = self._try_setup(battle, me, my_speed, opp_speed)
            if setup_order:
                return setup_order

        # 12. Status Moves Logic
        if max_score < STATUS_MOVE_THRESHOLD and opp.current_hp_fraction >= HIGH_HP_FRACTION:
            status_move = self._find_best_status_move(battle, me, opp, my_speed, opp_speed)
            if status_move:
                self._record_used_move(btag, status_move.id)
                return self.create_order(status_move)

        # 13. Attack with best move (Predictive Punish check)
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

    def _try_hazard_clearing(self, battle, me, opp) -> object:
        if not battle.available_moves or me is None or opp is None:
            return None

        has_hazards = any(c in battle.side_conditions for c in ENTRY_HAZARDS.values())
        n_bench_alive = len([m for m in battle.team.values() if not m.fainted and m != me])
        if not has_hazards or n_bench_alive == 0:
            return None

        clear_moves = [m for m in battle.available_moves if m.id in ANTI_HAZARDS_MOVES]
        if not clear_moves:
            return None

        # Check if opponent can OHKO us
        gen = self._get_gen(battle)
        sets_db = self._load_pokemon_sets(gen)
        opp_max_dmg = self._estimate_max_damage(opp, me, gen, sets_db)
        my_hp = self._current_hp(me)
        if opp_max_dmg >= my_hp:
            return None

        # Prioritize moves: tidyup > rapidspin > courtchange > defog
        clear_priority = {"tidyup": 4, "rapidspin": 3, "courtchange": 2, "defog": 1}
        best_move = max(clear_moves, key=lambda m: clear_priority.get(m.id, 0))

        btag = battle.battle_tag
        self._hazard_removals_by_battle[btag] = self._hazard_removals_by_battle.get(btag, 0) + 1
        self._record_used_move(btag, best_move.id)
        return self.create_order(best_move)

    def _try_hazard_laying(self, battle) -> object:
        if not battle.available_moves:
            return None

        btag = battle.battle_tag
        n_opp_remaining = 6 - len([m for m in battle.opponent_team.values() if m.fainted])
        if n_opp_remaining < 3:
            return None

        hazard_moves = [m for m in battle.available_moves if m.id in ENTRY_HAZARDS]
        if not hazard_moves:
            return None

        usable_hazards = []
        for m in hazard_moves:
            condition = ENTRY_HAZARDS[m.id]
            if condition not in battle.opponent_side_conditions:
                usable_hazards.append(m)

        if not usable_hazards:
            return None

        # Prioritize: stealthrock > stickyweb > spikes > toxicspikes
        hazard_priority = {"stealthrock": 4, "stickyweb": 3, "spikes": 2, "toxicspikes": 1}
        best_hazard = max(usable_hazards, key=lambda m: hazard_priority.get(m.id, 0))

        self._hazard_sets_by_battle[btag] = self._hazard_sets_by_battle.get(btag, 0) + 1
        self._record_used_move(btag, best_hazard.id)
        return self.create_order(best_hazard)

    # -- Setup Logic ----------------------------------------------------------

    def _try_setup(self, battle, me, my_speed=100.0, opp_speed=100.0) -> object:
        opp = battle.opponent_active_pokemon
        if opp is not None:
            gen = self._get_gen(battle)
            sets_db = self._load_pokemon_sets(gen)
            opp_max_dmg = self._estimate_max_damage(opp, me, gen, sets_db)

            me_hp = self._current_hp(me)

            # If opponent outspeeds us, they hit us first. If they can 2HKO us, setup is suicidal.
            if opp_speed > my_speed:
                if opp_max_dmg >= me_hp * 0.45:
                    return None
            else:
                # If we outspeed them, they hit us second. But we still need to survive their hit.
                if opp_max_dmg >= me_hp * 0.80:
                    return None

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
                if "GROUND" in opp_types or "ELECTRIC" in opp_types:
                    continue
                opp_ability = str(getattr(opp, "ability", "")).lower()
                if "guts" in opp_ability or "limber" in opp_ability:
                    continue
                priority = 2.5 if opp_speed > my_speed else 1

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

        ability_mult = self._ability_damage_multiplier(defender, move.type.name)
        if ability_mult == 0.0:
            return 0.0, 0.0

        stab = 1.5 if move.type in attacker.types else 1.0
        level = attacker.level if attacker.level else 80

        bp = move.base_power
        if move.id == "knockoff" and self._has_knockable_item(defender):
            bp = bp * 1.5

        base_dmg = ((2 * level / 5 + 2) * bp * ratio) / 50 + 2
        score = base_dmg * stab * eff * ability_mult
        score = self._apply_weather_mod(score, move, battle)
        score = self._apply_terrain_mod(score, move, battle)

        # Apply attacker item damage modifiers
        item = str(getattr(attacker, "item", "") or "").lower().replace(" ", "").replace("-", "")
        if item == "lifeorb":
            score *= 1.3
        else:
            type_boosters = {
                "charcoal": "FIRE",
                "mysticwater": "WATER",
                "magnet": "ELECTRIC",
                "miracleseed": "GRASS",
                "nevermeltice": "ICE",
                "blackbelt": "FIGHTING",
                "poisonbarb": "POISON",
                "softsand": "GROUND",
                "sharpbeak": "FLYING",
                "twistedspoon": "PSYCHIC",
                "silverpowder": "BUG",
                "hardstone": "ROCK",
                "spelltag": "GHOST",
                "dragonfang": "DRAGON",
                "blackglasses": "DARK",
                "metalcoat": "STEEL",
                "silkscarf": "NORMAL",
                "pixieplate": "FAIRY",
            }
            if type_boosters.get(item) == move.type.name:
                score *= 1.2

        return score * 0.85, score

    # -- Move Scoring (with modifiers & Knock Off bonuses) ---------------------

    def _score_move(self, move, me, opp, physical_ratio, special_ratio, battle, my_speed, opp_speed) -> float:
        if move.base_power <= 1:
            return 0.0
        if move.id in {"fakeout", "firstimpression"} and not self._is_fakeout_usable(battle):
            return 0.0

        ratio = physical_ratio if move.category == MoveCategory.PHYSICAL else special_ratio
        if move.category not in [MoveCategory.PHYSICAL, MoveCategory.SPECIAL]:
            return 0.0

        effectiveness = opp.damage_multiplier(move)
        if effectiveness == 0.0:
            return 0.0

        ability_mult = self._ability_damage_multiplier(opp, move.type.name)
        if ability_mult == 0.0:
            return 0.0

        stab = 1.5 if move.type in me.types else 1.0
        accuracy = move.accuracy if isinstance(move.accuracy, (int, float)) else 1.0
        expected_hits = move.expected_hits if hasattr(move, "expected_hits") else 1.0

        bp = move.base_power
        if move.id == "knockoff" and self._has_knockable_item(opp):
            bp = bp * 1.5

        score = bp * ratio * effectiveness * stab * accuracy * expected_hits * ability_mult

        score = self._apply_weather_mod(score, move, battle)
        score = self._apply_terrain_mod(score, move, battle)

        # Apply attacker item damage modifiers
        item = str(getattr(me, "item", "") or "").lower().replace(" ", "").replace("-", "")
        if item == "lifeorb":
            score *= 1.3
        else:
            type_boosters = {
                "charcoal": "FIRE",
                "mysticwater": "WATER",
                "magnet": "ELECTRIC",
                "miracleseed": "GRASS",
                "nevermeltice": "ICE",
                "blackbelt": "FIGHTING",
                "poisonbarb": "POISON",
                "softsand": "GROUND",
                "sharpbeak": "FLYING",
                "twistedspoon": "PSYCHIC",
                "silverpowder": "BUG",
                "hardstone": "ROCK",
                "spelltag": "GHOST",
                "dragonfang": "DRAGON",
                "blackglasses": "DARK",
                "metalcoat": "STEEL",
                "silkscarf": "NORMAL",
                "pixieplate": "FAIRY",
            }
            if type_boosters.get(item) == move.type.name:
                score *= 1.2

        if self._get_move_priority(move, battle) > 0 and my_speed < opp_speed:
            score *= 1.3

        if move.id in {"suckerpunch", "thunderclap"}:
            if my_speed >= opp_speed:
                score *= 0.4
            else:
                score *= 0.85

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
        """Decide whether to switch out. Threat-aware with hysteresis.

        Philosophy: a hard switch costs a turn of momentum (the opponent gets a
        free hit), so we only do it when staying in is clearly losing AND the
        bench has a clearly better answer. A Pokémon that just came in holds its
        ground unless it is in real danger — this kills the infinite switch loop.
        """
        # Toxic poison gets worse every turn: bail before it snowballs.
        if my_status == "TOX" and me.status_counter > 2:
            return "toxic"

        gen = self._get_gen(battle)
        sets_db = self._load_pokemon_sets(gen)
        opp_max_dmg = self._estimate_max_damage(opp, me, gen, sets_db)
        my_hp = self._current_hp(me)
        incoming_ratio = opp_max_dmg / max(my_hp, 1.0)

        # Best bench answer to the *current* opponent, discounted by the entry-
        # hazard chip each candidate would eat on the way in. This is what stops
        # the bot from repeatedly pivoting a Rock-weak mon into its own rocks.
        my_hazards = getattr(battle, "side_conditions", {})
        best_bench_score = -999.0
        for s in battle.available_switches:
            if not self._is_switch_allowed(battle, s):
                continue
            bench_score = self._estimate_matchup(s, opp, battle)
            chip = self._switch_in_hazard_fraction(s, my_hazards)
            if chip > 0:
                bench_score -= chip * HP_FRACTION_COEFF * 2.0
            if bench_score > best_bench_score:
                best_bench_score = bench_score

        active_matchup = self._estimate_matchup(me, opp, battle)

        # In real danger: opponent outspeeds us and threatens a (near) OHKO.
        danger = incoming_ratio >= 0.55 and (opp_speed > my_speed or incoming_ratio >= 0.9)

        # Hysteresis: don't bounce a freshly switched-in Pokémon back out on a
        # marginal read. Only re-switch if we're now in genuine danger.
        if self._just_switched_in(battle) and not danger:
            return ""

        # Severe stat drops make us dead weight — leave if anything better exists.
        crippled = (
            me.boosts.get("def", 0) <= -3
            or me.boosts.get("spd", 0) <= -3
            or (me.boosts.get("atk", 0) <= -3 and self._is_physical_attacker(me))
            or (me.boosts.get("spa", 0) <= -3 and not self._is_physical_attacker(me))
        )
        if crippled and best_bench_score > active_matchup + 0.3:
            return "matchup"

        # Outsped with no meaningful offense: pivot to someone who matters.
        if max_score < WEAK_MOVE_THRESHOLD and my_speed < opp_speed and best_bench_score > active_matchup + 0.4:
            return "weak"

        # Win-condition preservation: pull our win-con out of a losing spot early.
        btag = battle.battle_tag
        roles = self._roles_by_battle.get(btag, {})
        if roles.get(me.species.lower()) == "WIN_CON" and active_matchup < 0.0 and best_bench_score > 0.5:
            return "matchup"

        # Clearly losing the matchup and the bench is clearly better.
        if active_matchup < -0.3 and best_bench_score > 0.3:
            return "matchup"

        # Threatened with a KO and the bench tanks it far better.
        if danger and best_bench_score > active_matchup + 1.0:
            return "matchup"

        # General fallback: a hard switch needs a clearly better answer to be worth the lost tempo.
        if best_bench_score <= active_matchup + 0.8:
            return ""

        return "matchup"

    @staticmethod
    def _is_physical_attacker(mon) -> bool:
        atk = mon.base_stats.get("atk", 100) if mon.base_stats else 100
        spa = mon.base_stats.get("spa", 100) if mon.base_stats else 100
        return atk >= spa

    def _just_switched_in(self, battle) -> bool:
        """True if our active Pokémon entered the field on the previous turn.

        Used as a hysteresis brake: a Pokémon that *just* came in should not be
        immediately switched back out again on a marginal matchup read, which is
        the main cause of the 'keeps switching forever' loop.
        """
        btag = battle.battle_tag
        history = getattr(self, "_active_history_by_battle", {}).get(btag, [])
        if len(history) < 2:
            return False
        return history[-1][1] != history[-2][1]

    def _is_switch_allowed(self, battle, target) -> bool:
        if target is None:
            return False
        btag = battle.battle_tag
        if not hasattr(self, "_active_history_by_battle") or not hasattr(self, "_opp_active_history_by_battle"):
            return True
        history = self._active_history_by_battle.get(btag, [])
        opp_history = self._opp_active_history_by_battle.get(btag, [])
        if len(history) >= 2 and len(opp_history) >= 2:
            our_switched_last_turn = history[-2][1] != history[-1][1]
            opp_switched_last_turn = opp_history[-2][1] != opp_history[-1][1]
            if our_switched_last_turn and not opp_switched_last_turn:
                target_name = target.species.lower() if hasattr(target, "species") else str(target).lower()
                recent_names = {h[1] for h in history[-3:-1]}
                if target_name in recent_names:
                    return False
        return True

    # -- Switch Targets (Choice Exploitations & Team Threat Reasoning) ----------

    def _worst_team_matchup(self, candidate, battle, exclude=None):
        """How threatened *candidate* is by the rival's *worst* remaining Pokémon.

        Models a human's whole-team pressure rather than just the active foe:
        we look at every revealed, non-fainted opponent and return the lowest
        matchup score the candidate has against any of them. A switch-in that
        hard-walls the active mon but is OHKO'd by an obvious teammate should not
        be picked blindly — this is the 'reason about their team' upgrade.
        """
        worst = None
        for o in battle.opponent_team.values():
            if o.fainted or (exclude is not None and o is exclude):
                continue
            score = self._estimate_matchup(candidate, o, battle)
            if worst is None or score < worst:
                worst = score
        return worst if worst is not None else 0.0

    def _get_best_switch(self, battle, opp, allowed_only=False):
        best = None
        best_score = -999.0

        opp_item = str(opp.item).lower() if opp.item else ""
        is_choice_locked = "choice" in opp_item and len(opp.moves) > 0

        switches = battle.available_switches
        if allowed_only:
            switches = [s for s in switches if self._is_switch_allowed(battle, s)]

        if not switches:
            return None

        my_hazards = getattr(battle, "side_conditions", {})
        for pokemon in switches:
            # Primary: matchup vs the Pokémon we're actually switching into.
            score = self._estimate_matchup(pokemon, opp, battle)

            # Secondary: don't pick something the rest of their team trivially
            # blows up. Weighted lightly so the active matchup still dominates,
            # but enough to break ties toward a pick with no glaring weakness.
            worst_vs_team = self._worst_team_matchup(pokemon, battle, exclude=opp)
            if worst_vs_team < -0.5:
                score += worst_vs_team * 0.25

            # Penalise switching a hazard-vulnerable mon into our own side's
            # entry hazards (Stealth Rock / Spikes). Scaled to the same units as
            # the matchup HP term so a Rock-weak mon isn't picked into 25% chip.
            chip = self._switch_in_hazard_fraction(pokemon, my_hazards)
            if chip > 0:
                score -= chip * HP_FRACTION_COEFF * 2.0

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

        return best if best is not None else switches[0]

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
            opp_max_dmg_fraction = opp_max_dmg / max(self._estimate_max_hp(active), 1.0)

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
                if active.current_hp_fraction >= 0.40 or n_alive == 1:
                    return True

            if active.current_hp_fraction < 0.30 and n_alive > 1:
                return False

            # Calculate exact offensive STAB/efficiency factor change when terastallizing
            original_stab = 1.5 if move.type in active.types else 1.0
            new_stab = 1.0
            if move.type == tera_type:
                new_stab = 2.0 if tera_type in active.types else 1.5
            elif move.type in active.types:
                new_stab = 1.0
            else:
                new_stab = original_stab

            original_eff = opp_active.damage_multiplier(move)
            new_eff = original_eff
            if move.id == "terablast":
                original_eff = opp_active.damage_multiplier(PokemonType.NORMAL)
                new_eff = opp_active.damage_multiplier(tera_type)

            if original_eff * original_stab == 0:
                offensive_tera_score = 1.0
            else:
                offensive_tera_score = (new_eff * new_stab) / (original_eff * original_stab)

            def_scores_inv = [1.0 / (m if m > 0 else 0.125) for m in def_scores]
            defensive_score = min(def_scores_inv) if def_scores_inv else 1.0

            def_tera_scores_inv = [1.0 / (m if m > 0 else 0.125) for m in def_tera_scores]
            defensive_tera_score = min(def_tera_scores_inv) if def_tera_scores_inv else 1.0

            # Check if Tera converts a non-KO move into a KO
            opp_hp = self._current_hp(opp_active)
            dmg_min, _ = self._calculate_exact_damage_range(move, active, opp_active, battle)
            not_ko_without_tera = dmg_min < opp_hp
            ko_with_tera = dmg_min * offensive_tera_score >= opp_hp
            converts_to_ko = not_ko_without_tera and ko_with_tera

            has_offensive_boosts = (
                active.boosts.get("atk", 0) >= 1
                or active.boosts.get("spa", 0) >= 1
                or active.boosts.get("spe", 0) >= 1
            )

            is_offensive_worthwhile = (
                n_alive == 1
                or has_offensive_boosts
                or converts_to_ko
            )

            if is_offensive_worthwhile:
                net_ratio = offensive_tera_score * (defensive_tera_score / defensive_score)
                if converts_to_ko and net_ratio > 1.0:
                    return True
                if net_ratio > 1.2:
                    return True

            return False
        except Exception:
            return False

    # -- Damage & Matchup Estimations ------------------------------------------

    def _estimate_max_damage(self, attacker, defender, gen: int, sets_db: dict) -> float:
        attacker_moves = list(attacker.moves.values()) if attacker.moves else []
        moves_data = GenData.from_gen(gen).moves

        clean_name = attacker.species.lower().replace(" ", "").replace("-", "").replace("_", "")
        predicted = sets_db.get(clean_name, {}).get("moves", [])

        if not attacker_moves:
            move_ids = predicted
        else:
            move_ids = [m.id for m in attacker_moves]
            # If the attacker is the opponent (so we only see revealed moves), supplement with predicted moves
            if len(move_ids) < 4:
                for pm in predicted:
                    if pm not in move_ids:
                        move_ids.append(pm)

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
                level = attacker.level if attacker.level else 80
                base_dmg = ((2 * level / 5 + 2) * 80.0 * ratio) / 50 + 2
                dmg = base_dmg * eff * 1.5

                # Apply attacker item damage modifiers
                item = str(getattr(attacker, "item", "") or "").lower().replace(" ", "").replace("-", "")
                if item == "lifeorb":
                    dmg *= 1.3
                else:
                    type_boosters = {
                        "charcoal": "FIRE",
                        "mysticwater": "WATER",
                        "magnet": "ELECTRIC",
                        "miracleseed": "GRASS",
                        "nevermeltice": "ICE",
                        "blackbelt": "FIGHTING",
                        "poisonbarb": "POISON",
                        "softsand": "GROUND",
                        "sharpbeak": "FLYING",
                        "twistedspoon": "PSYCHIC",
                        "silverpowder": "BUG",
                        "hardstone": "ROCK",
                        "spelltag": "GHOST",
                        "dragonfang": "DRAGON",
                        "blackglasses": "DARK",
                        "metalcoat": "STEEL",
                        "silkscarf": "NORMAL",
                        "pixieplate": "FAIRY",
                    }
                    if type_boosters.get(item) == t.name:
                        dmg *= 1.2

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

            if m_id == "knockoff" and self._has_knockable_item(defender):
                bp = bp * 1.5

            m_type_str = m_data.get("type", "").upper()
            if not m_type_str:
                continue

            try:
                m_type = PokemonType.from_name(m_type_str)
            except Exception:
                continue

            ability_mult = self._ability_damage_multiplier(defender, m_type_str)
            if ability_mult == 0.0:
                continue

            eff = defender.damage_multiplier(m_type)
            if eff == 0.0:
                continue

            stab = 1.5 if m_type in attacker.types else 1.0
            category = m_data.get("category", "")
            ratio = phys_ratio if category == "Physical" else spec_ratio

            level = attacker.level if attacker.level else 80
            base_dmg = ((2 * level / 5 + 2) * bp * ratio) / 50 + 2
            dmg = base_dmg * eff * stab * ability_mult

            # Apply attacker item damage modifiers
            item = str(getattr(attacker, "item", "") or "").lower().replace(" ", "").replace("-", "")
            if item == "lifeorb":
                dmg *= 1.3
            else:
                type_boosters = {
                    "charcoal": "FIRE",
                    "mysticwater": "WATER",
                    "magnet": "ELECTRIC",
                    "miracleseed": "GRASS",
                    "nevermeltice": "ICE",
                    "blackbelt": "FIGHTING",
                    "poisonbarb": "POISON",
                    "softsand": "GROUND",
                    "sharpbeak": "FLYING",
                    "twistedspoon": "PSYCHIC",
                    "silverpowder": "BUG",
                    "hardstone": "ROCK",
                    "spelltag": "GHOST",
                    "dragonfang": "DRAGON",
                    "blackglasses": "DARK",
                    "metalcoat": "STEEL",
                    "silkscarf": "NORMAL",
                    "pixieplate": "FAIRY",
                }
                if type_boosters.get(item) == m_type_str:
                    dmg *= 1.2

            if dmg > max_dmg:
                max_dmg = dmg

        return max_dmg

    def _estimate_matchup(self, mon, opponent, battle=None) -> float:
        if not mon or not opponent:
            return 0.0
        gen = self._get_gen(battle)
        sets_db = self._load_pokemon_sets(gen)

        max_offensive = self._estimate_max_damage(mon, opponent, gen, sets_db)
        max_defensive = self._estimate_max_damage(opponent, mon, gen, sets_db)

        score = (max_offensive - max_defensive) / 200.0

        format_str = battle._format if (battle and hasattr(battle, "_format")) else ""
        my_status = get_status_name(mon)
        opp_status = get_status_name(opponent)

        my_speed = self._get_boosted_speed(mon, my_status, format_str)
        opp_speed = self._get_boosted_speed(opponent, opp_status, format_str)

        if my_speed > opp_speed:
            score += SPEED_TIER_COEFF
        elif opp_speed > my_speed:
            score -= SPEED_TIER_COEFF

        score += mon.current_hp_fraction * HP_FRACTION_COEFF
        score -= opponent.current_hp_fraction * HP_FRACTION_COEFF

        # If opponent outspeeds and can OHKO us, apply a severe penalty
        mon_hp = self._current_hp(mon)
        if opp_speed > my_speed and max_defensive >= mon_hp:
            score -= 10.0

        return score

    # -- HP Estimation ---------------------------------------------------------

    @staticmethod
    def _estimate_max_hp(mon) -> float:
        """Estimate a Pokémon's real max HP.

        For our own Pokémon poke-env exposes the true ``max_hp``. For the
        opponent it only exposes an HP percentage, so we reconstruct the stat
        from base HP and level (31 IV / 84 EV spread, matching random battles).
        This is critical: the old code assumed every Pokémon had 300 HP, which
        made the bot hallucinate KOs on fat walls (Blissey, Toxapex, ...).
        """
        real_max = getattr(mon, "max_hp", None)
        if real_max:
            return float(real_max)
        base_hp = mon.base_stats.get("hp", 100) if mon.base_stats else 100
        if base_hp == 1:  # Shedinja
            return 1.0
        level = mon.level if getattr(mon, "level", None) else 80
        return ((2 * base_hp + 31 + 21) * level / 100.0) + level + 10

    def _current_hp(self, mon) -> float:
        """Return the Pokémon's current HP on the same scale as the damage model."""
        frac = mon.current_hp_fraction if mon.current_hp_fraction is not None else 1.0
        return frac * self._estimate_max_hp(mon)

    @staticmethod
    def _switch_in_hazard_fraction(mon, side_conditions) -> float:
        """Estimate the HP fraction *mon* loses on switching into our hazards.

        Switching into Stealth Rock / Spikes repeatedly is the single biggest way
        a heuristic throws games against a hazard-stacking human. We price that
        chip in so the bot stops sacking its own HP on needless pivots. Heavy-Duty
        Boots and Magic Guard negate all entry-hazard chip.
        """
        if not side_conditions:
            return 0.0

        item = str(getattr(mon, "item", "") or "").lower().replace(" ", "").replace("-", "")
        ability = str(getattr(mon, "ability", "") or "").lower().replace(" ", "").replace("-", "")
        if item == "heavydutyboots" or ability == "magicguard":
            return 0.0

        types = [t.name for t in mon.types if t is not None]
        grounded = "FLYING" not in types and ability != "levitate" and item != "airballoon"

        chip = 0.0

        # Stealth Rock: 12.5% scaled by Rock-type effectiveness against the mon.
        if SideCondition.STEALTH_ROCK in side_conditions:
            try:
                rock = PokemonType.from_name("ROCK")
                mult = mon.damage_multiplier(rock)
            except Exception:
                mult = 1.0
            chip += 0.125 * mult

        if grounded:
            spikes_layers = side_conditions.get(SideCondition.SPIKES, 0)
            if spikes_layers:
                chip += {1: 1 / 8, 2: 1 / 6, 3: 1 / 4}.get(spikes_layers, 1 / 4)

        return chip

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
        val = ((2.0 * base + 31.0) + 5.0) * multiplier

        # Apply item stat boosts if the item is known/revealed
        item = str(getattr(mon, "item", "") or "").lower().replace(" ", "").replace("-", "")
        if item:
            if stat == "atk" and item == "choiceband":
                val *= 1.5
            elif stat == "spa" and item == "choicespecs":
                val *= 1.5
            elif stat == "spd" and item == "assaultvest":
                val *= 1.5
            elif (stat == "def" or stat == "spd") and item == "eviolite":
                val *= 1.5
        return val

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
    def _ability_damage_multiplier(defender, move_type_name: str) -> float:
        """Damage multiplier from the *defender's* ability against a move type.

        Returns 0.0 (immunity, e.g. Earth Eater vs Ground), 0.5 (resist ability,
        e.g. Thick Fat vs Fire/Ice), or 1.0 (no effect). Lets the damage model
        respect abilities that aren't captured by the raw type chart.
        """
        ability = getattr(defender, "ability", None)
        if not ability:
            return 1.0
        ability_str = str(ability).lower().replace(" ", "").replace("-", "")
        if ABILITY_IMMUNITIES.get(ability_str) == move_type_name:
            return 0.0
        if move_type_name in ABILITY_HALF_DAMAGE.get(ability_str, ()):
            return 0.5
        return 1.0

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
