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
from poke_env.player.battle_order import BattleOrder
from p00_core.core.common import get_status_name
from p01_heuristics.agents.internal.v14 import HeuristicV14


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


class HeuristicV17MCTS(HeuristicV14):
    """Information Set Monte Carlo Tree Search Agent (Base).

    Uses pokechamp's LocalSim for fast in-process rollouts.
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

    def _get_greedy_rollout_action(self, battle, is_opponent: bool) -> Any:
        """A fast, type-aware greedy rollout action picker."""
        if not is_opponent:
            active = battle.active_pokemon
            target = battle.opponent_active_pokemon
            if not active or active.fainted:
                switches = battle.available_switches
                return random.choice(switches) if switches else None

            moves = battle.available_moves
            if moves:
                def score_move(m):
                    bp = m.base_power or 0
                    if target:
                        return bp * target.damage_multiplier(m)
                    return bp
                return max(moves, key=score_move)

            switches = battle.available_switches
            return random.choice(switches) if switches else None
        else:
            active = battle.opponent_active_pokemon
            target = battle.active_pokemon
            opp_switches = [p for p in battle.opponent_team.values() if not p.active and not p.fainted]
            if not active or active.fainted:
                return random.choice(opp_switches) if opp_switches else None

            # Opponent moves are in active.moves
            moves = list(active.moves.values())
            if moves:
                def score_move(m):
                    bp = m.base_power or 0
                    if target:
                        return bp * target.damage_multiplier(m)
                    return bp
                return max(moves, key=score_move)

            return random.choice(opp_switches) if opp_switches else None

    def _sample_opponent_determinization(self, battle, sets_db: dict) -> dict[str, Any]:
        """Samples plausible moves for the opponent based on Showdown sets database."""
        opp_team_data = {}
        gen = self._get_gen(battle)
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

        # Apply the sampled opponent determinization to sim's opponent team
        for mon in sim.battle.opponent_team.values():
            spec = mon.species
            if spec in opp_determinization:
                det = opp_determinization[spec]
                mon._ability = det["ability"]
                mon._item = det["item"]
                # Update moves
                for m_id in det["moves"]:
                    if m_id not in mon.moves:
                        try:
                            mon._moves[m_id] = Move(m_id, gen=self._get_gen(battle))
                        except Exception:
                            pass

        # First step
        my_first_order = self.create_order(initial_action)
        opp_first_action = self._get_greedy_rollout_action(sim.battle, is_opponent=True)
        opp_first_order = self.create_order(opp_first_action) if opp_first_action else None

        sim.step(my_first_order, opp_first_order)

        # Rollout loop
        for _ in range(self.ROLLOUT_DEPTH - 1):
            if sim.battle.finished or not sim.battle.active_pokemon or not sim.battle.opponent_active_pokemon:
                break

            my_action = self._get_greedy_rollout_action(sim.battle, is_opponent=False)
            opp_action = self._get_greedy_rollout_action(sim.battle, is_opponent=True)

            my_order = self.create_order(my_action) if my_action else None
            opp_order = self.create_order(opp_action) if opp_action else None

            if not my_order and not opp_order:
                break

            sim.step(my_order, opp_order)

        if sim.battle.won:
            return 2.0
        if sim.battle.lost:
            return -2.0

        # Evaluate the terminal state: sum of HP percentages of active + benched (assuming unrevealed are at 100% HP)
        def get_team_hp(team):
            revealed_hp = sum(p.current_hp_fraction for p in team.values())
            unrevealed_count = max(0, 6 - len(team))
            return (revealed_hp + unrevealed_count) / 6.0

        me_hp_sum = get_team_hp(sim.battle.team)
        opp_hp_sum = get_team_hp(sim.battle.opponent_team)

        return me_hp_sum - opp_hp_sum

    def _select_action(self, battle):
        me = battle.active_pokemon
        opp = battle.opponent_active_pokemon

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

        # 2. Guaranteed KO — always execute immediately
        format_str = battle._format or ""
        my_status = get_status_name(me)
        opp_status = get_status_name(opp)
        my_speed = self._get_boosted_speed(me, my_status, format_str)
        opp_speed = self._get_boosted_speed(opp, opp_status, format_str)

        ko_move = self._find_guaranteed_ko(battle, me, opp, my_speed, opp_speed)
        if ko_move:
            self._ko_checks_by_battle[battle.battle_tag] = (
                self._ko_checks_by_battle.get(battle.battle_tag, 0) + 1
            )
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
            except Exception as e:
                # Fallback to heuristic evaluation on failure
                import traceback
                traceback.print_exc()
                score = 0.0

            # Backpropagate
            node.visits += 1
            node.value += score
            root.visits += 1

        # Select action with the highest visit count (robust child)
        best_node = max(root.children, key=lambda n: n.visits)
        best_action = best_node.action

        if best_action:
            if not isinstance(best_action, Move):
                # Switch action
                return self.create_order(best_action)
            else:
                # Move action
                self._record_used_move(battle.battle_tag, best_action.id)
                tera = self._should_terastallize(battle, best_action)
                return self.create_order(best_action, terastallize=tera)

        return self.choose_random_move(battle)
