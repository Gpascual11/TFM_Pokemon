from __future__ import annotations

import math
import random
from typing import Any

try:
    from poke_env.environment.move import Move
except ImportError:
    from poke_env.battle import Move

from p00_core.core.common import get_status_name
from .v16_minimax import HeuristicV16Minimax


class HeuristicV17MinimaxHybrid(HeuristicV16Minimax):
    """Minimax Agent v17_minimax_hybrid (Hybrid Guided Search with Heuristic Prior Biasing)."""

    def __init__(self, **kwargs):
        self.heuristic_prior_weight: float = kwargs.pop("heuristic_prior_weight", 0.15)
        super().__init__(**kwargs)

    def _get_v14_pure_action(self, battle):
        from src.p01_heuristics.agents.internal.v14 import HeuristicV14
        btag = battle.battle_tag
        hist = list(getattr(self, "_active_history_by_battle", {}).get(btag, []))
        opp_hist = list(getattr(self, "_opp_active_history_by_battle", {}).get(btag, []))
        last_m = getattr(self, "_last_turn_matchup", {}).get(btag)
        move_counts_us = dict(getattr(battle, "move_counts_us", {}))
        fallback_cnt = getattr(self, "_fallback_moves_by_battle", {}).get(btag, 0)
        error_cnt = getattr(self, "_error_moves_by_battle", {}).get(btag, 0)

        try:
            order = HeuristicV14._select_action(self, battle)
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
        if hasattr(self, "_fallback_moves_by_battle") and btag in self._fallback_moves_by_battle:
            self._fallback_moves_by_battle[btag] = fallback_cnt
        if hasattr(self, "_error_moves_by_battle") and btag in self._error_moves_by_battle:
            self._error_moves_by_battle[btag] = error_cnt

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
        opp_status = get_status_name(opp) if opp else "HEALTHY"

        my_speed = self._get_boosted_speed(me, my_status, format_str)
        opp_speed = self._get_boosted_speed(opp, opp_status, format_str) if opp else 100.0

        gen = self._get_gen(battle)
        sets_db = self._load_pokemon_sets(gen)

        if opp:
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

            # Early game scouting check
            if battle.turn <= 3 and hasattr(self, "_is_switch_allowed"):
                for m in battle.available_moves:
                    if m.id in {"uturn", "voltswitch", "flipturn"} and battle.available_switches:
                        opp_max_dmg = 0.0
                        if hasattr(self, "_estimate_max_damage"):
                            opp_max_dmg = self._estimate_max_damage(opp, me, gen, sets_db)
                        if opp_max_dmg < me.current_hp * 0.55:
                            self._record_used_move(btag, m.id)
                            return self.create_order(m)

        my_actions: list[Any] = list(battle.available_moves)
        if battle.available_switches and opp:
            for switch_cand in battle.available_switches:
                if self._is_switch_allowed(battle, switch_cand):
                    my_actions.append(switch_cand)
        if not my_actions:
            return self.choose_random_move(battle)

        opp_actions: list[Any] = []
        if opp:
            opp_actions = self._predict_opponent_moves(battle, opp, gen, sets_db)
            has_switches = any(not p.fainted and not p.active for p in battle.opponent_team.values())
            if has_switches:
                opp_actions.append("switch")

        # Compute baseline v14 prior for Heuristic Prior Biasing (Hybrid Guided Search)
        v14_order = self._get_v14_pure_action(battle)
        v14_target = v14_order.order if v14_order else None
        v14_id = getattr(v14_target, "id", getattr(v14_target, "species", str(v14_target))) if v14_target else None

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

            # Apply Heuristic Prior Biasing bonus (+0.15 by default) to v14's expert recommendation
            act_id = getattr(my_action, "id", getattr(my_action, "species", str(my_action)))
            if v14_target is not None and (my_action == v14_target or act_id == v14_id):
                worst_case_score_for_this_action += self.heuristic_prior_weight

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
