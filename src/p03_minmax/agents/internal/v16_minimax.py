from __future__ import annotations

import math
import random
from typing import Any

try:
    from poke_env.environment.move import Move
    from poke_env.environment.move_category import MoveCategory
except ImportError:
    from poke_env.battle import Move, MoveCategory

from p00_core.core.common import get_status_name
from p01_heuristics.agents.internal.v14 import HeuristicV14

SETUP_MOVES = {
    "swordsdance",
    "dragondance",
    "nastyplot",
    "calmmind",
    "quiverdance",
    "shiftgear",
    "curse",
    "bulkup",
    "agility",
    "shellsmash",
    "irondefense",
}
HAZARD_MOVES = {"stealthrock", "spikes", "toxicspikes", "stickyweb"}
RECOVERY_MOVES = {"recover", "roost", "slackoff", "softboiled", "moonlight", "synthesis", "shoreup"}
HAZARD_REMOVAL_MOVES = {"rapidspin", "defog", "tidyup", "courtchange"}


class HeuristicV16Minimax(HeuristicV14):
    """Upgraded 1-Ply Adversarial Minimax Agent using Heuristic V14 Scored Evaluator.

    Integrates setup, hazard, and recovery bonuses from HeuristicV14 into the minimax state scoring.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._search_switches_by_battle: dict[str, int] = {}
        self._search_moves_by_battle: dict[str, int] = {}
        self._endgame_solves_by_battle: dict[str, int] = {}
        self._search_diff_by_battle: dict[str, int] = {}
        self._total_turns_by_battle: dict[str, int] = {}
        self._last_action_type: dict[str, int] = {}
        self._loop_guards_by_battle: dict[str, int] = {}

    def _predict_opponent_moves(self, battle, opp, gen: int, sets_db: dict) -> list[Move]:
        opp_moves = list(opp.moves.values()) if opp.moves else []
        move_objs = {m.id: m for m in opp_moves}

        if len(move_objs) < 4:
            clean_name = opp.species.lower().replace(" ", "").replace("-", "").replace("_", "")
            predicted_ids = sets_db.get(clean_name, {}).get("moves", [])
            candidate_moves = []
            for pid in predicted_ids:
                if pid not in move_objs:
                    try:
                        m = Move(pid, gen=gen)
                        bp = m.base_power or 0
                        score = bp * (opp.damage_multiplier(m) if opp else 1.0)
                        if m.category == MoveCategory.STATUS:
                            score = 40.0
                        candidate_moves.append((score, m))
                    except Exception:
                        pass
            candidate_moves.sort(key=lambda x: x[0], reverse=True)
            needed = 4 - len(move_objs)
            for _, m in candidate_moves[:needed]:
                move_objs[m.id] = m

        return list(move_objs.values())

    def _predict_opponent_best_switch_in(self, battle, me) -> Any:
        best_counter = None
        best_score = -999.0
        for s in battle.opponent_team.values():
            if s.fainted or s.active:
                continue
            score = self._estimate_matchup(s, me, battle)
            if score > best_score:
                best_score = score
                best_counter = s
        return best_counter

    def _evaluate_state_score(
        self,
        battle,
        my_action: Any,
        opp_action: Any,
        me,
        opp,
        gen: int,
        sets_db: dict,
    ) -> float:
        # Guard: no opponent move predicted (empty moveset + no bench). Return a
        # simple HP-differential score so minimax can still rank our actions.
        if opp_action is None:
            is_my_switch = not isinstance(my_action, Move)
            me_hp = my_action.current_hp_fraction if is_my_switch else me.current_hp_fraction
            return me_hp - 1.5 * opp.current_hp_fraction

        is_my_switch = not isinstance(my_action, Move)
        is_opp_switch = opp_action == "switch"

        # Utility bonuses
        action_bonus = 0.0

        # Apply entry hazard chip damage penalties for switches
        my_hazards = getattr(battle, "side_conditions", {})

        # 1. BOTH PLAYERS SWITCH
        if is_my_switch and is_opp_switch:
            switch_in = my_action
            opp_switch_in = self._predict_opponent_best_switch_in(battle, me)
            if not opp_switch_in:
                opp_switch_in = opp

            # Deduct entry hazard chip damage on entry
            my_chip = self._switch_in_hazard_fraction(switch_in, my_hazards)
            me_hp_pct = max(0.0, switch_in.current_hp_fraction - my_chip)
            opp_hp_pct = opp_switch_in.current_hp_fraction
            matchup_score = self._estimate_matchup(switch_in, opp_switch_in, battle)

            return me_hp_pct - 1.5 * opp_hp_pct + 0.3 * matchup_score

        # 2. WE SWITCH, OPPONENT ATTACKS
        if is_my_switch and not is_opp_switch:
            switch_in = my_action
            opp_move = opp_action

            opp_dmg = 0.0
            if opp_move.base_power > 0 and opp_move.category in [MoveCategory.PHYSICAL, MoveCategory.SPECIAL]:
                _, opp_dmg = self._calculate_exact_damage_range(opp_move, opp, switch_in, battle)

            my_chip = self._switch_in_hazard_fraction(switch_in, my_hazards)
            incoming_current_hp = max(0.0, switch_in.current_hp - opp_dmg - (my_chip * switch_in.max_hp))
            me_hp_pct = max(0.0, incoming_current_hp / switch_in.max_hp) if switch_in.max_hp > 0 else 0.0
            opp_hp_pct = opp.current_hp_fraction
            matchup_score = self._estimate_matchup(switch_in, opp, battle)

            return me_hp_pct - 1.5 * opp_hp_pct + 0.3 * matchup_score

        # 3. WE ATTACK, OPPONENT SWITCHES
        if not is_my_switch and is_opp_switch:
            my_move = my_action
            opp_switch_in = self._predict_opponent_best_switch_in(battle, me)
            if not opp_switch_in:
                opp_switch_in = opp

            my_dmg = 0.0
            if my_move.base_power > 0 and my_move.category in [MoveCategory.PHYSICAL, MoveCategory.SPECIAL]:
                if not self._is_ability_immune(my_move, opp_switch_in):
                    _, my_dmg = self._calculate_exact_damage_range(my_move, me, opp_switch_in, battle)

            # Award bonuses for setup/hazards/recovery
            if my_move.id in SETUP_MOVES:
                action_bonus += 0.3
            elif my_move.id in HAZARD_MOVES:
                action_bonus += 0.25
            elif my_move.id in HAZARD_REMOVAL_MOVES and len(my_hazards) > 0:
                action_bonus += 0.25
            elif my_move.id in RECOVERY_MOVES and me.current_hp_fraction < 0.7:
                action_bonus += 0.35

            me_hp_pct = me.current_hp_fraction
            opp_incoming_hp = opp_switch_in.current_hp - my_dmg
            opp_hp_pct = max(0.0, opp_incoming_hp / opp_switch_in.max_hp) if opp_switch_in.max_hp > 0 else 0.0
            matchup_score = self._estimate_matchup(opp_switch_in, me, battle)

            return me_hp_pct - 1.5 * opp_hp_pct - 0.3 * matchup_score + action_bonus

        # 4. BOTH ATTACK
        my_move = my_action
        opp_move = opp_action

        my_protects = my_move.id in {"protect", "detect", "banefulbunker", "kingsshield", "spikyshield", "silkerape", "burningbulwark"}
        opp_protects = opp_move.id in {"protect", "detect", "banefulbunker", "kingsshield", "spikyshield", "silkerape", "burningbulwark"}

        my_dmg = 0.0
        if not opp_protects and my_move.base_power > 0 and my_move.category in [MoveCategory.PHYSICAL, MoveCategory.SPECIAL]:
            if not self._is_ability_immune(my_move, opp):
                _, my_dmg = self._calculate_exact_damage_range(my_move, me, opp, battle)

        opp_dmg = 0.0
        if not my_protects and opp_move.base_power > 0 and opp_move.category in [MoveCategory.PHYSICAL, MoveCategory.SPECIAL]:
            if not self._is_ability_immune(opp_move, me):
                _, opp_dmg = self._calculate_exact_damage_range(opp_move, opp, me, battle)

        # Resolve priority and speed order
        my_priority = self._get_move_priority(my_move, battle)
        opp_priority = opp_move.entry.get("priority", 0) if opp_move.entry else 0

        my_status = get_status_name(me)
        opp_status = get_status_name(opp)
        format_str = battle._format or ""
        my_speed = self._get_boosted_speed(me, my_status, format_str)
        opp_speed = self._get_boosted_speed(opp, opp_status, format_str)

        my_hits_first = True
        if my_priority > opp_priority:
            my_hits_first = True
        elif opp_priority > my_priority:
            my_hits_first = False
        else:
            if my_speed > opp_speed:
                my_hits_first = True
            elif opp_speed > my_speed:
                my_hits_first = False
            else:
                my_hits_first = False

        if my_hits_first:
            opp_remaining_hp = opp.current_hp - my_dmg
            if opp_remaining_hp <= 0:
                opp_dmg = 0.0
        else:
            me_remaining_hp = me.current_hp - opp_dmg
            if me_remaining_hp <= 0:
                my_dmg = 0.0

        healing_bonus_hp = 0.0
        if my_move.id in RECOVERY_MOVES:
            healing_bonus_hp = 0.5 * me.max_hp if me.current_hp_fraction < 0.85 else 0.0
        elif my_move.id in {"gigadrain", "drainpunch", "hornleech", "bitterblade", "drainingkiss", "paraboliccharge", "matchagotcha", "oblivionwing"}:
            healing_bonus_hp = 0.5 * my_dmg

        if my_hits_first:
            incoming_hp = min(me.max_hp, me.current_hp + healing_bonus_hp) - opp_dmg
            me_after_hp = max(0.0, min(1.0, incoming_hp / me.max_hp)) if me.max_hp > 0 else 0.0
        else:
            me_remaining_hp = me.current_hp - opp_dmg
            if me_remaining_hp <= 0:
                me_after_hp = 0.0
            else:
                incoming_hp = min(me.max_hp, me_remaining_hp + healing_bonus_hp)
                me_after_hp = max(0.0, min(1.0, incoming_hp / me.max_hp)) if me.max_hp > 0 else 0.0

        opp_after_hp = max(0.0, (opp.current_hp - my_dmg) / opp.max_hp) if opp.max_hp > 0 else 0.0

        # Apply action bonuses
        if my_move.id in SETUP_MOVES:
            action_bonus += 0.3
        elif my_move.id in HAZARD_MOVES:
            action_bonus += 0.25
        elif my_move.id in HAZARD_REMOVAL_MOVES and len(my_hazards) > 0:
            action_bonus += 0.25
        elif my_move.id in RECOVERY_MOVES and me.current_hp_fraction < 0.7:
            action_bonus += 0.35

        # Status bonuses
        status_bonus = 0.0
        if my_move.category == MoveCategory.STATUS and my_move.id in {"willowisp", "thunderwave", "toxic", "spore"}:
            if opp.status is None and not self._is_ability_immune(my_move, opp):
                status_bonus += 0.2

        if opp_move.category == MoveCategory.STATUS and opp_move.id in {"willowisp", "thunderwave", "toxic", "spore"}:
            if me.status is None and not self._is_ability_immune(opp_move, me):
                status_bonus -= 0.3

        return me_after_hp - 1.5 * opp_after_hp + status_bonus + action_bonus

    def _get_v14_pure_action(self, battle):
        btag = battle.battle_tag
        hist = list(getattr(self, "_active_history_by_battle", {}).get(btag, []))
        opp_hist = list(getattr(self, "_opp_active_history_by_battle", {}).get(btag, []))
        last_m = getattr(self, "_last_turn_matchup", {}).get(btag)
        move_counts_us = dict(getattr(battle, "move_counts_us", {}))

        try:
            order = super()._select_action(battle)
        except Exception:
            order = None

        if hasattr(self, "_active_history_by_battle") and btag in self._active_history_by_battle:
            self._active_history_by_battle[btag] = hist
        if hasattr(self, "_opp_active_history_by_battle") and btag in self._opp_active_history_by_battle:
            self._opp_active_history_by_battle[btag] = opp_hist
        if hasattr(self, "_last_turn_matchup"):
            if last_m is not None:
                self._last_turn_matchup[btag] = last_m
            elif btag in self._last_turn_matchup:
                del self._last_turn_matchup[btag]
        if hasattr(battle, "move_counts_us"):
            battle.move_counts_us = move_counts_us

        return order

    def _select_action(self, battle):
        btag = battle.battle_tag
        me = battle.active_pokemon
        opp = battle.opponent_active_pokemon

        self._total_turns_by_battle[btag] = self._total_turns_by_battle.get(btag, 0) + 1

        self._evaluate_team_roles(battle)
        self._update_inferences(battle)

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
        my_status = get_status_name(me)
        opp_status = get_status_name(opp)
        my_speed = self._get_boosted_speed(me, my_status, format_str)
        opp_speed = self._get_boosted_speed(opp, opp_status, format_str)

        ko_move = self._find_guaranteed_ko(battle, me, opp, my_speed, opp_speed)
        if ko_move:
            self._ko_checks_by_battle[btag] = self._ko_checks_by_battle.get(btag, 0) + 1
            self._record_used_move(btag, ko_move.id)
            tera = self._should_terastallize(battle, ko_move)
            return self.create_order(ko_move, terastallize=tera)

        endgame_order = self._run_endgame_solver(battle, me, opp)
        if endgame_order:
            self._endgame_solves_by_battle[btag] = self._endgame_solves_by_battle.get(btag, 0) + 1
            return endgame_order

        # Emergency tactical checks from V14
        if hasattr(self, "_handle_opponent_setup_sweeper"):
            setup_order = self._handle_opponent_setup_sweeper(battle, me, opp, my_speed, opp_speed)
            if setup_order:
                return setup_order

        if hasattr(self, "_try_status_absorption"):
            status_order = self._try_status_absorption(battle, me, opp)
            if status_order:
                return status_order

        gen = self._get_gen(battle)
        sets_db = self._load_pokemon_sets(gen)

        # Early game scouting check
        if battle.turn <= 3 and hasattr(self, "_is_switch_allowed"):
            for m in battle.available_moves:
                if m.id in {"uturn", "voltswitch", "flipturn"} and battle.available_switches:
                    # Check if safe to pivot
                    opp_max_dmg = 0.0
                    if opp and hasattr(self, "_estimate_max_damage"):
                        opp_max_dmg = self._estimate_max_damage(opp, me, gen, sets_db)
                    if opp_max_dmg < me.current_hp * 0.55:
                        self._record_used_move(btag, m.id)
                        return self.create_order(m)

        # Minimax adversarial search

        my_actions: list[Any] = list(battle.available_moves)
        if battle.available_switches and opp:
            for switch_cand in battle.available_switches:
                if self._is_switch_allowed(battle, switch_cand):
                    my_actions.append(switch_cand)
        if not my_actions:
            return self.choose_random_move(battle)

        opp_actions: list[Any] = self._predict_opponent_moves(battle, opp, gen, sets_db)
        if battle.opponent_team:
            has_switches = any(not p.fainted and not p.active for p in battle.opponent_team.values())
            if has_switches:
                opp_actions.append("switch")

        best_action = None
        best_worst_case_score = -math.inf

        for my_action in my_actions:
            worst_case_score_for_this_action = math.inf

            if not opp_actions:
                score = self._evaluate_state_score(battle, my_action, None, me, opp, gen, sets_db)
                worst_case_score_for_this_action = score
            else:
                for opp_action in opp_actions:
                    score = self._evaluate_state_score(battle, my_action, opp_action, me, opp, gen, sets_db)
                    if score < worst_case_score_for_this_action:
                        worst_case_score_for_this_action = score

            if worst_case_score_for_this_action > best_worst_case_score:
                best_worst_case_score = worst_case_score_for_this_action
                best_action = my_action

        is_switch = best_action is not None and not isinstance(best_action, Move)
        last_action = self._last_action_type.get(btag, 0)
        if is_switch and last_action == 1 and battle.available_moves:
            # Prevent infinite switch loops by forcing the best move instead
            best_move_score = -math.inf
            best_move_action = None
            for move in battle.available_moves:
                if not opp_actions:
                    score = self._evaluate_state_score(battle, move, None, me, opp, gen, sets_db)
                else:
                    score = min(
                        self._evaluate_state_score(battle, move, o_act, me, opp, gen, sets_db)
                        for o_act in opp_actions
                    )
                if score > best_move_score:
                    best_move_score = score
                    best_move_action = move
            if best_move_action is not None:
                best_action = best_move_action
            else:
                best_action = random.choice(list(battle.available_moves))
            self._loop_guards_by_battle[btag] = self._loop_guards_by_battle.get(btag, 0) + 1
            is_switch = False

        self._last_action_type[btag] = 1 if is_switch else 0

        if best_action:
            if not isinstance(best_action, Move):
                self._search_switches_by_battle[btag] = self._search_switches_by_battle.get(btag, 0) + 1
                actual_order = self.create_order(best_action)
            else:
                self._search_moves_by_battle[btag] = self._search_moves_by_battle.get(btag, 0) + 1
                self._record_used_move(btag, best_action.id)
                tera = self._should_terastallize(battle, best_action)
                actual_order = self.create_order(best_action, terastallize=tera)
        else:
            actual_order = self.choose_random_move(battle)

        # Track search difference vs raw v14 heuristic
        try:
            v14_order = self._get_v14_pure_action(battle)
        except Exception:
            v14_order = None

        if v14_order and actual_order:
            v14_act = v14_order.order
            act_act = actual_order.order

            v14_id = (
                v14_act.id
                if hasattr(v14_act, "id")
                else (v14_act.species if hasattr(v14_act, "species") else str(v14_act))
            )
            act_id = (
                act_act.id
                if hasattr(act_act, "id")
                else (act_act.species if hasattr(act_act, "species") else str(act_act))
            )

            if v14_id != act_id:
                self._search_diff_by_battle[btag] = self._search_diff_by_battle.get(btag, 0) + 1

        return actual_order

    def reset_battles(self) -> None:
        try:
            super().reset_battles()
        finally:
            self._search_switches_by_battle.clear()
            self._search_moves_by_battle.clear()
            self._endgame_solves_by_battle.clear()
            self._search_diff_by_battle.clear()
            self._total_turns_by_battle.clear()
            self._last_action_type.clear()
            self._loop_guards_by_battle.clear()
