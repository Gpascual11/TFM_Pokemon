from __future__ import annotations

import math
import random
import sys
from pathlib import Path
from typing import Any

# Inject pokechamp path to resolve all standard poke_env imports from the fork
project_root = Path(__file__).parent.parent.parent.parent.parent.resolve()
pokechamp_path = project_root / "pokechamp"
if str(pokechamp_path) not in sys.path:
    sys.path.insert(0, str(pokechamp_path))
    # Force eviction of already loaded PyPI poke_env modules from cache
    for key in list(sys.modules.keys()):
        if key == "poke_env" or key.startswith("poke_env."):
            sys.modules.pop(key)

from poke_env.environment.move import Move
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


class MCTSNode:
    """A node in the Monte Carlo Search Tree."""

    def __init__(self, action: Any = None, parent: MCTSNode | None = None):
        self.action = action  # Move or Pokemon object
        self.parent = parent
        self.children: list[MCTSNode] = []
        self.visits = 0
        self.value = 0.0

    def ucb_score(self, exploration_c: float = 1.4) -> float:
        if self.visits == 0:
            return float("inf")
        exploitation = self.value / self.visits
        exploration = exploration_c * math.sqrt(math.log(self.parent.visits) / self.visits)
        return exploitation + exploration


class HeuristicV18MCTS(HeuristicV14):
    """Information Set Monte Carlo Tree Search Agent (Base).

    Uses pokechamp's LocalSim for fast in-process rollouts with tactical action selection
    and state-preserving telemetry tracking against V14 recommendations.
    """

    N_SIMULATIONS = 100
    ROLLOUT_DEPTH = 5
    EXPLORATION_C = 1.4

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        from pokechamp.data_cache import (
            get_cached_move_effect,
            get_cached_pokemon_move_dict,
            get_cached_ability_effect,
            get_cached_pokemon_ability_dict,
            get_cached_item_effect,
            get_cached_pokemon_item_dict,
        )

        self.move_effect = get_cached_move_effect()
        self.pokemon_move_dict = get_cached_pokemon_move_dict()
        self.ability_effect = get_cached_ability_effect()
        self.pokemon_ability_dict = get_cached_pokemon_ability_dict()
        self.item_effect = get_cached_item_effect()
        self.pokemon_item_dict = get_cached_pokemon_item_dict()

        self._search_switches_by_battle: dict[str, int] = {}
        self._search_moves_by_battle: dict[str, int] = {}
        self._endgame_solves_by_battle: dict[str, int] = {}
        self._search_diff_by_battle: dict[str, int] = {}
        self._total_turns_by_battle: dict[str, int] = {}
        self._last_action_type: dict[str, int] = {}
        self._loop_guards_by_battle: dict[str, int] = {}

    def _get_v14_pure_action(self, battle):
        """Safely queries HeuristicV14 recommendation without corrupting state tracking."""
        btag = battle.battle_tag
        hist = list(getattr(self, "_active_history_by_battle", {}).get(btag, []))
        opp_hist = list(getattr(self, "_opp_active_history_by_battle", {}).get(btag, []))
        last_m = getattr(self, "_last_turn_matchup", {}).get(btag)
        move_counts_us = dict(getattr(battle, "move_counts_us", {}))

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

        return order

    def _get_greedy_rollout_action(self, battle, is_opponent: bool) -> Any:
        """A fast, type-aware and tactical greedy rollout action picker for MCTS."""
        if not is_opponent:
            active = battle.active_pokemon
            target = battle.opponent_active_pokemon
            switches = list(battle.available_switches)
            if not active or active.fainted:
                return random.choice(switches) if switches else None

            moves = [m for m in battle.available_moves if getattr(m, "current_pp", 1) > 0]
            if not moves:
                return random.choice(switches) if switches else None

            # Tactical switch check during rollout if heavily crippled or facing severe unfavorable matchup
            if switches and target and not target.fainted:
                try:
                    hp_pct = active.current_hp_fraction
                    if getattr(active, "boosts", {}).get("atk", 0) <= -2 and getattr(active, "boosts", {}).get("spa", 0) <= -2:
                        return random.choice(switches)
                    max_my_mult = max((target.damage_multiplier(m) for m in moves if getattr(m, "base_power", 0) > 0), default=1.0)
                    if max_my_mult <= 0.5 and hp_pct < 0.6 and random.random() < 0.4:
                        return random.choice(switches)
                except Exception:
                    pass

            def score_move(m):
                bp = m.base_power or 0
                if bp > 0:
                    mult = target.damage_multiplier(m) if target else 1.0
                    score = bp * mult
                    if getattr(m, "type", None) and (getattr(active, "type_1", None) == m.type or getattr(active, "type_2", None) == m.type):
                        score *= 1.5
                    return score
                m_id = m.id
                if m_id in SETUP_MOVES:
                    hp_pct = active.current_hp_fraction if active else 1.0
                    return 80.0 if hp_pct > 0.75 else 20.0
                if m_id in RECOVERY_MOVES:
                    hp_pct = active.current_hp_fraction if active else 1.0
                    return 90.0 if hp_pct < 0.55 else 10.0
                if m_id in HAZARD_MOVES:
                    return 70.0 if getattr(battle, "turn", 1) <= 3 else 25.0
                if m_id in HAZARD_REMOVAL_MOVES:
                    hazards = getattr(battle, "side_conditions", {})
                    return 75.0 if hazards else 15.0
                return 15.0

            return max(moves, key=score_move)
        else:
            active = battle.opponent_active_pokemon
            target = battle.active_pokemon
            opp_switches = [p for p in battle.opponent_team.values() if not p.active and not p.fainted]
            if not active or active.fainted:
                return random.choice(opp_switches) if opp_switches else None

            moves = [m for m in active.moves.values() if getattr(m, "current_pp", 1) > 0]
            if not moves:
                return random.choice(opp_switches) if opp_switches else None

            if opp_switches and target and not target.fainted:
                try:
                    hp_pct = active.current_hp_fraction
                    max_opp_mult = max((target.damage_multiplier(m) for m in moves if getattr(m, "base_power", 0) > 0), default=1.0)
                    if max_opp_mult <= 0.5 and hp_pct < 0.6 and random.random() < 0.35:
                        return random.choice(opp_switches)
                except Exception:
                    pass

            def score_move(m):
                bp = m.base_power or 0
                if bp > 0:
                    mult = target.damage_multiplier(m) if target else 1.0
                    score = bp * mult
                    if getattr(m, "type", None) and (getattr(active, "type_1", None) == m.type or getattr(active, "type_2", None) == m.type):
                        score *= 1.5
                    return score
                m_id = m.id
                if m_id in SETUP_MOVES:
                    hp_pct = active.current_hp_fraction if active else 1.0
                    return 80.0 if hp_pct > 0.75 else 20.0
                if m_id in RECOVERY_MOVES:
                    hp_pct = active.current_hp_fraction if active else 1.0
                    return 90.0 if hp_pct < 0.55 else 10.0
                if m_id in HAZARD_MOVES:
                    return 70.0 if getattr(battle, "turn", 1) <= 3 else 25.0
                if m_id in HAZARD_REMOVAL_MOVES:
                    hazards = getattr(battle, "opponent_side_conditions", {})
                    return 75.0 if hazards else 15.0
                return 15.0

            return max(moves, key=score_move)

    def _sample_opponent_determinization(self, battle, sets_db: dict) -> dict[str, Any]:
        """Samples plausible moves for the opponent based on Showdown sets database."""
        opp_team_data = {}
        for mon in battle.opponent_team.values():
            species_clean = mon.species.lower().replace(" ", "").replace("-", "").replace("_", "")
            set_info = sets_db.get(species_clean, {})
            probable_moves = set_info.get("moves", [])

            # Fill up to 4 moves
            mon_moves = list(mon.moves.keys())
            for m_id in probable_moves:
                if len(mon_moves) >= 4:
                    break
                if m_id not in mon_moves:
                    mon_moves.append(m_id)

            opp_team_data[mon.species] = {
                "moves": mon_moves,
                "ability": mon.ability or set_info.get("ability", ""),
                "item": mon.item or set_info.get("item", ""),
            }
        return opp_team_data

    def _rollout(self, battle, initial_action: Any, opp_determinization: dict) -> float:
        """Simulates ROLLOUT_DEPTH turns using LocalSim and returns team HP difference."""
        from poke_env.player.local_simulation import LocalSim
        from poke_env.data.gen_data import GenData

        gen_data = GenData.from_format(battle._format or "gen9randombattle")

        # Instantiate a local battle copy
        sim = LocalSim(
            battle,
            self.move_effect,
            self.pokemon_move_dict,
            self.ability_effect,
            self.pokemon_ability_dict,
            self.item_effect,
            self.pokemon_item_dict,
            gen_data,
            self._dynamax_disable,
            format=battle._format or "gen9randombattle",
        )

        # Apply the sampled opponent determinization to sim's opponent team and active pokemon
        for mon in list(sim.battle.opponent_team.values()) + ([sim.battle.opponent_active_pokemon] if sim.battle.opponent_active_pokemon else []):
            if not mon:
                continue
            spec = mon.species
            if spec in opp_determinization:
                det = opp_determinization[spec]
                mon._ability = det["ability"]
                mon._item = det["item"]
                for m_id in det["moves"]:
                    if m_id not in mon.moves:
                        try:
                            mon._moves[m_id] = Move(m_id, gen=self._get_gen(battle))
                        except Exception:
                            pass

        # First step
        my_first_order = self.create_order(initial_action) if initial_action else None
        opp_first_action = self._get_greedy_rollout_action(sim.battle, is_opponent=True)
        opp_first_order = self.create_order(opp_first_action) if opp_first_action else None

        if my_first_order and opp_first_order:
            sim.step(my_first_order, opp_first_order)

            # Rollout loop
            for _ in range(self.ROLLOUT_DEPTH - 1):
                if sim.battle.finished or not sim.battle.active_pokemon or not sim.battle.opponent_active_pokemon:
                    break

                my_action = self._get_greedy_rollout_action(sim.battle, is_opponent=False)
                opp_action = self._get_greedy_rollout_action(sim.battle, is_opponent=True)

                my_order = self.create_order(my_action) if my_action else None
                opp_order = self.create_order(opp_action) if opp_action else None

                if not my_order or not opp_order:
                    break

                sim.step(my_order, opp_order)

        if sim.battle.won:
            return 2.0
        if sim.battle.lost:
            return -2.0

        return self._evaluate_mcts_terminal_state(sim)

    def _evaluate_mcts_terminal_state(self, sim) -> float:
        """Evaluates the terminal state of an MCTS rollout (Base V18 evaluation)."""
        def get_team_hp(team):
            revealed_hp = sum(p.current_hp_fraction for p in team.values())
            unrevealed_count = max(0, 6 - len(team))
            return (revealed_hp + unrevealed_count) / 6.0

        me_hp_sum = get_team_hp(sim.battle.team)
        opp_hp_sum = get_team_hp(sim.battle.opponent_team)

        # Active boost bonus
        me_active = sim.battle.active_pokemon
        opp_active = sim.battle.opponent_active_pokemon
        boost_bonus = 0.0
        if me_active and not me_active.fainted and hasattr(me_active, "boosts"):
            pos_boosts = sum(max(0, v) for k, v in me_active.boosts.items() if k in {"atk", "spa", "spe"})
            boost_bonus += 0.04 * pos_boosts
        if opp_active and not opp_active.fainted and hasattr(opp_active, "boosts"):
            opp_boosts = sum(max(0, v) for k, v in opp_active.boosts.items() if k in {"atk", "spa", "spe"})
            boost_bonus -= 0.04 * opp_boosts

        # Status condition advantage
        status_bonus = 0.0
        if opp_active and getattr(opp_active, "status", None) is not None:
            status_bonus += 0.08
        if me_active and getattr(me_active, "status", None) is not None:
            status_bonus -= 0.08

        # Hazard control check
        hazard_bonus = 0.0
        if sum(sim.battle.opponent_side_conditions.values()) > 0:
            hazard_bonus += 0.05
        if sum(sim.battle.side_conditions.values()) > 0:
            hazard_bonus -= 0.05

        return (me_hp_sum - opp_hp_sum) + boost_bonus + status_bonus + hazard_bonus

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
                # Best-switch returned None but switches exist — pick any available
                return self.create_order(battle.available_switches[0])
            # No switches at all — random is correct (last mon standing)
            return self.choose_random_move(battle)

        # 2. Guaranteed KO — always execute immediately
        format_str = battle._format or ""
        my_status = get_status_name(me)
        opp_status = get_status_name(opp)
        my_speed = self._get_boosted_speed(me, my_status, format_str)
        opp_speed = self._get_boosted_speed(opp, opp_status, format_str)

        ko_move = self._find_guaranteed_ko(battle, me, opp, my_speed, opp_speed)
        if ko_move:
            self._ko_checks_by_battle[battle.battle_tag] = self._ko_checks_by_battle.get(battle.battle_tag, 0) + 1
            self._record_used_move(battle.battle_tag, ko_move.id)
            tera = self._should_terastallize(battle, ko_move)
            return self.create_order(ko_move, terastallize=tera)

        # 3. Information Set MCTS Search Loop
        my_actions = list(battle.available_moves) + list(battle.available_switches)
        if not my_actions:
            return self.choose_random_move(battle)

        # Initialize root node and children
        root = MCTSNode()
        root.children = [MCTSNode(action=act, parent=root) for act in my_actions]

        gen = self._get_gen(battle)
        sets_db = self._load_pokemon_sets(gen)

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
