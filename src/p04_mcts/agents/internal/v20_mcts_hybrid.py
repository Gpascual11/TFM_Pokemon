"""MCTS Agent v20 (PUCT Information Set MCTS with Heuristic Prior Biasing).

Extends HeuristicV18MCTS with PUCT (Predictor Upper Confidence Bound for Trees).
Before MCTS expands root nodes, it queries the domain-expert recommendation of `HeuristicV14`.
The candidate action recommended by `v14` receives a strong initial prior probability (`heuristic_prior_weight = 0.70`),
guaranteeing that MCTS concentrates its simulation budget on high-value positional lines immediately.
"""

from __future__ import annotations

import math
import random
from typing import Any

try:
    from poke_env.environment.move import Move
except ImportError:
    from poke_env.battle import Move

from .v19_mcts import HeuristicV19MCTS, MCTSNode


class PUCTNode(MCTSNode):
    """A node in the PUCT Monte Carlo Search Tree with Heuristic Prior Biasing."""

    def __init__(self, action: Any = None, parent: PUCTNode | None = None, prior: float = 0.0):
        super().__init__(action=action, parent=parent)
        self.prior = prior

    def ucb_score(self, exploration_c: float = 1.4) -> float:
        if self.visits == 0:
            return float("inf") if self.prior == 0 else 1000.0 + self.prior * 100.0
        exploitation = self.value / self.visits
        if self.prior > 0:
            exploration = exploration_c * self.prior * math.sqrt(self.parent.visits) / (1 + self.visits)
        else:
            exploration = exploration_c * math.sqrt(math.log(self.parent.visits) / self.visits)
        return exploitation + exploration


class HeuristicV20MCTSHybrid(HeuristicV19MCTS):
    """PUCT Information Set MCTS Agent (Hybrid Guided Search)."""

    def __init__(self, **kwargs):
        self.heuristic_prior_weight: float = kwargs.pop("heuristic_prior_weight", 0.70)
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

        self._total_turns_by_battle[btag] = self._total_turns_by_battle.get(btag, 0) + 1

        my_actions = list(battle.available_moves) + list(battle.available_switches)
        if not my_actions:
            return self.choose_random_move(battle)

        # Query baseline v14 prior for PUCT Heuristic Prior Biasing
        try:
            v14_order = super()._select_action(battle)
        except Exception:
            v14_order = None
        v14_target = v14_order.order if v14_order else None

        # Initialize root node with PUCT children
        root = PUCTNode()
        n_children = len(my_actions)
        prior_expert = self.heuristic_prior_weight
        prior_other = (1.0 - prior_expert) / max(1, n_children - 1) if n_children > 1 else 0.0

        root.children = []
        for act in my_actions:
            p = prior_expert if (v14_target is not None and act == v14_target) else prior_other
            root.children.append(PUCTNode(action=act, parent=root, prior=p))

        gen = self._get_gen(battle)
        sets_db = self._load_pokemon_sets(gen)

        for _ in range(self.N_SIMULATIONS):
            # Selection: Pick child node maximizing PUCT score
            node = max(root.children, key=lambda n: n.ucb_score(self.EXPLORATION_C))

            # Determinization: Sample plausible opponent state
            opp_determinization = self._sample_opponent_determinization(battle, sets_db)

            # Rollout
            try:
                score = self._rollout(battle, node.action, opp_determinization)
            except Exception:
                score = 0.0

            # Backpropagate
            node.visits += 1
            node.value += score
            root.visits += 1

        # Select action with highest visit count
        best_node = max(root.children, key=lambda n: n.visits)
        best_action = best_node.action

        is_switch = best_action is not None and not isinstance(best_action, Move)
        last_action = self._last_action_type.get(btag, 0)
        if is_switch and last_action == 1 and battle.available_moves:
            # Prevent infinite switch loops by forcing the best move from MCTS tree or greedy rollout
            move_children = [c for c in root.children if c.action is not None and isinstance(c.action, Move)]
            if move_children:
                best_node = max(move_children, key=lambda n: n.visits)
                best_action = best_node.action
            else:
                best_action = self._get_greedy_rollout_action(battle, is_opponent=False) or random.choice(list(battle.available_moves))
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
