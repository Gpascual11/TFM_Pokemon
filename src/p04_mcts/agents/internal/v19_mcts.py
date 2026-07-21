from __future__ import annotations

import random
import sys
from pathlib import Path
from typing import Any

# Inject pokechamp path to resolve all standard poke_env imports from the fork
project_root = Path(__file__).parent.parent.parent.parent.parent.resolve()
pokechamp_path = project_root / "pokechamp"
if str(pokechamp_path) not in sys.path:
    sys.path.insert(0, str(pokechamp_path))
    for key in list(sys.modules.keys()):
        if key == "poke_env" or key.startswith("poke_env."):
            sys.modules.pop(key)

from poke_env.environment.move import Move
from p00_core.core.common import get_status_name
from .v18_mcts import HeuristicV18MCTS, MCTSNode


class HeuristicV19MCTS(HeuristicV18MCTS):
    """Information Set Monte Carlo Tree Search Agent (Upgraded).

    Extends HeuristicV18MCTS by introducing:
    1. Advanced V14-Guided Positional Scorer at leaf nodes (dynamic team roles, speed tier OHKO threat detection,
       status severity penalties, setup stages, and hazard control).
    2. V14 Emergency Tactical Overrides pre-search (setup stopping, status absorption, and early pivots).
    """

    def _evaluate_mcts_terminal_state(self, sim) -> float:
        """Evaluates the terminal state of an MCTS rollout (Advanced V19 Positional Scorer)."""
        battle = sim.battle
        me_team = battle.team
        opp_team = battle.opponent_team

        # 1. Dynamic Roles Weighted HP Score
        def get_weighted_team_hp(team, is_us: bool):
            total_hp = 0.0
            roles_map = getattr(self, "_roles_by_battle", {}).get(battle.battle_tag, {}) if is_us else {}
            for mon_id, mon in team.items():
                hp_frac = mon.current_hp_fraction
                weight = 1.0
                if is_us:
                    role = roles_map.get(mon_id, roles_map.get(mon.species, ""))
                    if role == "Win-Con":
                        weight = 1.45
                    elif role == "Vital Wall":
                        weight = 1.25
                total_hp += hp_frac * weight
            unrevealed_count = max(0, 6 - len(team))
            total_hp += unrevealed_count * 1.0
            return total_hp / 6.0

        me_hp_score = get_weighted_team_hp(me_team, is_us=True)
        opp_hp_score = get_weighted_team_hp(opp_team, is_us=False)
        hp_diff = me_hp_score - 1.2 * opp_hp_score

        me_active = battle.active_pokemon
        opp_active = battle.opponent_active_pokemon

        # 2. Matchup & Speed Tier / OHKO Threat Check
        matchup_score = 0.0
        threat_penalty = 0.0
        if me_active and opp_active and not me_active.fainted and not opp_active.fainted:
            matchup_score = self._estimate_matchup(me_active, opp_active, battle)
            try:
                gen = self._get_gen(battle)
                sets_db = self._load_pokemon_sets(gen)
                format_str = battle._format or ""
                my_status = get_status_name(me_active)
                opp_status = get_status_name(opp_active)
                my_speed = self._get_boosted_speed(me_active, my_status, format_str)
                opp_speed = self._get_boosted_speed(opp_active, opp_status, format_str)

                # If opponent outspeeds and can OHKO or severely cripple our active
                if opp_speed > my_speed:
                    max_defensive = self._estimate_max_damage(opp_active, me_active, gen, sets_db)
                    mon_hp = self._current_hp(me_active)
                    if max_defensive >= mon_hp:
                        roles_map = getattr(self, "_roles_by_battle", {}).get(battle.battle_tag, {})
                        spec_clean = me_active.species.lower()
                        role = roles_map.get(spec_clean, roles_map.get(me_active.species, ""))
                        threat_penalty = -10.0 if role in ["WIN_CON", "Win-Con"] else -6.5
            except Exception:
                pass

        # 3. Status Conditions Penalty / Reward
        status_score = 0.0
        for p in me_team.values():
            if p.status:
                s_name = p.status.name.lower()
                status_score -= 0.18 if s_name in {"brn", "par", "slp", "frz", "tox"} else 0.10
        for p in opp_team.values():
            if p.status:
                s_name = p.status.name.lower()
                status_score += 0.18 if s_name in {"brn", "par", "slp", "frz", "tox"} else 0.10

        # 4. Setup & Boosts Check
        boost_score = 0.0
        if me_active and not me_active.fainted and hasattr(me_active, "boosts"):
            pos_boosts = sum(max(0, v) for k, v in me_active.boosts.items() if k in {"atk", "spa", "spe"})
            boost_score += 0.06 * pos_boosts
        if opp_active and not opp_active.fainted and hasattr(opp_active, "boosts"):
            opp_boosts = sum(max(0, v) for k, v in opp_active.boosts.items() if k in {"atk", "spa", "spe"})
            boost_score -= 0.07 * opp_boosts

        # 5. Entry Hazard Chip & Control Check
        hazard_score = 0.0
        if sum(battle.opponent_side_conditions.values()) > 0:
            hazard_score += 0.08
        if sum(battle.side_conditions.values()) > 0:
            hazard_score -= 0.08

        return hp_diff + 0.35 * matchup_score + threat_penalty + status_score + boost_score + hazard_score

    def _select_action(self, battle):
        me = battle.active_pokemon
        opp = battle.opponent_active_pokemon
        btag = battle.battle_tag

        self._total_turns_by_battle[btag] = self._total_turns_by_battle.get(btag, 0) + 1

        # 1. Update roles and parse battlefield state
        self._evaluate_team_roles(battle)
        self._update_inferences(battle)

        # Handle forced switch scenarios
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

        # 2. Guaranteed KO & Tactical Overrides — always execute immediately
        format_str = battle._format or ""
        my_status = get_status_name(me)
        opp_status = get_status_name(opp)
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

            # V14 Emergency Setup Sweeper Stop
            if hasattr(self, "_handle_opponent_setup_sweeper"):
                setup_order = self._handle_opponent_setup_sweeper(battle, me, opp, my_speed, opp_speed)
                if setup_order:
                    return setup_order

            # V14 Status Absorption Pivot
            if hasattr(self, "_try_status_absorption"):
                status_order = self._try_status_absorption(battle, me, opp)
                if status_order:
                    return status_order

            # Early game scouting pivot check on turns 1-3
            if battle.turn <= 3 and hasattr(self, "_is_switch_allowed"):
                for m in battle.available_moves:
                    if m.id in {"uturn", "voltswitch", "flipturn"} and battle.available_switches:
                        opp_max_dmg = 0.0
                        if hasattr(self, "_estimate_max_damage"):
                            opp_max_dmg = self._estimate_max_damage(opp, me, gen, sets_db)
                        if opp_max_dmg < me.current_hp * 0.55:
                            self._record_used_move(btag, m.id)
        # 3. Information Set MCTS Search Loop
        my_actions = list(battle.available_moves) + list(battle.available_switches)
        if not my_actions:
            return self.choose_random_move(battle)

        # Initialize root node and children
        root = MCTSNode()
        root.children = [MCTSNode(action=act, parent=root) for act in my_actions]

        for _ in range(self.N_SIMULATIONS):
            # Selection: Pick child node maximizing UCB1
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

        # Select action with the highest visit count (robust child)
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
                self._record_used_move(battle.battle_tag, best_action.id)
                tera = self._should_terastallize(battle, best_action)
                actual_order = self.create_order(best_action, terastallize=tera)
        else:
            actual_order = self.choose_random_move(battle)

        # Track search difference vs raw v14 heuristic
        v14_order = self._get_v14_pure_action(battle)
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
