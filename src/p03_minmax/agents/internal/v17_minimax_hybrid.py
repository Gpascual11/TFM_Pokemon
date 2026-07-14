from __future__ import annotations

import math
import random
from typing import Any

try:
    from poke_env.environment.move import Move
except ImportError:
    from poke_env.battle import Move

from .v16_minimax import HeuristicV16Minimax


class HeuristicV17MinimaxHybrid(HeuristicV16Minimax):
    """Minimax Agent v17_minimax_hybrid (Hybrid Guided Search with Heuristic Prior Biasing)."""

    def __init__(self, **kwargs):
        self.heuristic_prior_weight: float = kwargs.pop("heuristic_prior_weight", 0.15)
        super().__init__(**kwargs)

    def _select_action(self, battle):
        btag = battle.battle_tag
        me = battle.active_pokemon
        opp = battle.opponent_active_pokemon

        if me is None or me.fainted or not battle.available_moves:
            return super()._select_action(battle)

        format_str = battle._format or ""
        my_status = getattr(me, "status", None)
        my_status_name = my_status.name.lower() if my_status else None
        opp_status = getattr(opp, "status", None) if opp else None
        opp_status_name = opp_status.name.lower() if opp_status else None

        my_speed = self._get_boosted_speed(me, my_status_name, format_str)
        opp_speed = self._get_boosted_speed(opp, opp_status_name, format_str) if opp else 100.0

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

        gen = self._get_gen(battle)
        sets_db = self._load_pokemon_sets(gen)
        self._total_turns_by_battle[btag] = self._total_turns_by_battle.get(btag, 0) + 1

        my_actions: list[Any] = list(battle.available_moves)
        if battle.available_switches and opp:
            for switch_cand in battle.available_switches:
                if self._is_switch_allowed(battle, switch_cand):
                    my_actions.append(switch_cand)

        opp_actions: list[Any] = []
        if opp:
            opp_actions = self._predict_opponent_moves(battle, opp, gen, sets_db)
            has_switches = any(not p.fainted and not p.active for p in battle.opponent_team.values())
            if has_switches:
                opp_actions.append("switch")

        # Compute baseline v14 prior for Heuristic Prior Biasing (Hybrid Guided Search)
        try:
            v14_order = super()._select_action(battle)
        except Exception:
            v14_order = None
        v14_target = v14_order.order if v14_order else None

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
            if v14_target is not None and my_action == v14_target:
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
