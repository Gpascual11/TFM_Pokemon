from __future__ import annotations

import math
from p01_heuristics.s01_singles.core.common import calculate_base_damage, get_speed, get_status_name
from p01_heuristics.s01_singles.core.base import BaseHeuristic1v1

class HeuristicV7Minimax(BaseHeuristic1v1):
    """1-Ply Minimax (Adversarial Search) Agent.
    
    Unlike V1-V6 which are purely greedy algorithms (maximizing immediate damage),
    V7 evaluates every legal move against the opponent's *best possible* legal response.
    
    It simulates a 1-turn lookahead:
    1. For every legal action A we can take:
        2. For every legal action B the opponent can take:
            3. Evaluate the board state resulting from A -> B.
        4. Find the worst-case scenario (minimum score) for action A.
    5. Choose the action A that has the highest worst-case score (Maximin).
    """

    def _evaluate_state(self, battle, my_move, opp_move) -> float:
        """
        Calculates a static evaluation $V(s)$ of the hypothetical state 
        after my_move and opp_move are executed.
        
        Args:
            battle (AbstractBattle): The current battle state.
            my_move (Move | Pokemon | None): The action chosen by the agent. Can be an attack move, a switch (Pokemon object), or None.
            opp_move (Move | None): The hypothetical move chosen by the opponent.
            
        Returns:
            float: A continuous score representing the desirability of the board state. Positive values indicate an advantage for the agent.
        """
        me = battle.active_pokemon
        opp = battle.opponent_active_pokemon
        
        my_status = get_status_name(me)
        opp_status = get_status_name(opp)
        
        # 1. Base Damage I deal
        my_damage_dealt = 0
        if my_move is not None and my_move.category.name != "STATUS":
            # Using our existing heuristic damage calculator
            my_damage_dealt = calculate_base_damage(my_move, me, opp, my_status)
            
            # Factor in priority/speed
            my_speed = get_speed(me, my_status)
            opp_speed = get_speed(opp, opp_status)
            if my_speed > opp_speed or my_move.priority > 0:
                my_damage_dealt *= 1.2 # Bonus for hitting first
        
        # 2. Base Damage opponent deals to me
        opp_damage_dealt = 0
        if opp_move is not None and opp_move.category.name != "STATUS":
            # Estimate damage opponent deals to us
            opp_damage_dealt = calculate_base_damage(opp_move, opp, me, opp_status)
            
        # 3. Calculate Final Minimax Score
        # We want to MAXIMIZE our damage and MINIMIZE opponent damage.
        # If I deal 50 damage and opponent deals 10, State Score = +40
        # If I deal 10 damage and opponent deals 80, State Score = -70
        state_score = my_damage_dealt - (opp_damage_dealt * 1.5) # Weigh taking damage more heavily (risk averse)

        return state_score

    def _select_action(self, battle):
        """
        Executes a 1-ply Minimax search over the current game state to determine the optimal action.
        
        It iterates over all available legal actions (moves and switches) for the agent. For each action, 
        it simulates the opponent's "best" response (the action that minimizes the agent's score). 
        The agent then selects the action that maximizes this worst-case scenario (Maximin).
        
        Args:
            battle (AbstractBattle): The current active battle state from pokemon-showdown.
            
        Returns:
            BattleOrder: The chosen optimal action to dispatch to the server.
        """
        me = battle.active_pokemon
        opp = battle.opponent_active_pokemon

        if me is None or opp is None:
            return self.choose_random_move(battle)

        best_action = None
        best_worst_case_score = -math.inf

        my_actions = battle.available_moves + battle.available_switches
        
        # If we have no choices, just struggle or pass
        if not my_actions:
            return self.choose_random_move(battle)

        for my_action in my_actions:
            
            # If I switch, my "move" is None for damage calculation purposes
            is_my_switch = hasattr(my_action, "species")
            my_move = None if is_my_switch else my_action
            
            # Assume opponent has access to their visible moves (or random sample if unknown)
            # In a real POMDP we'd use the Bayesian predictor here! For now, we use known moves
            opp_known_moves = list(opp.moves.values())
            
            worst_case_score_for_this_action = math.inf
            
            if not opp_known_moves:
                 # If we know nothing about opponent, just evaluate our greedy move
                 score = self._evaluate_state(battle, my_move, None)
                 if is_my_switch:
                     score -= 30 # Small penalty for switching blind
                 worst_case_score_for_this_action = score
            else:
                # 1-Ply Minimax: Simulate opponent's best response
                for opp_move in opp_known_moves:
                    # Score the state from OUR perspective
                    score = self._evaluate_state(battle, my_move, opp_move)
                    
                    if is_my_switch:
                        # If we switch, the opponent gets a free hit on the incoming Pokemon
                        # (Because we don't know incoming stats perfectly without simulating the full engine,
                        # we heavily penalize taking a hit while switching out)
                        score -= 50
                        
                    # Opponent wants to MINIMIZE our score
                    if score < worst_case_score_for_this_action:
                        worst_case_score_for_this_action = score
                        
            # We want to MAXIMIZE our worst-case score
            if worst_case_score_for_this_action > best_worst_case_score:
                best_worst_case_score = worst_case_score_for_this_action
                best_action = my_action

        if best_action:
            if hasattr(best_action, "species"):
                return self.create_order(best_action)
            else:
                self._record_used_move(battle.battle_tag, best_action.id)
                return self.create_order(best_action)

        return self.choose_random_move(battle)
