from __future__ import annotations

import math
from typing import Any

try:
    from poke_env.environment.move import Move
    from poke_env.environment.move_category import MoveCategory
except ImportError:
    from poke_env.battle import Move, MoveCategory

from p00_core.core.common import get_status_name
from p01_heuristics.agents.internal.v14 import HeuristicV14


class HeuristicV15Minimax(HeuristicV14):
    """1-Ply Adversarial Minimax Agent using Heuristic V14 Evaluator & Showdown DB.

    This agent extends HeuristicV14 to perform a 1-ply adversarial lookahead
    over the current turn. It evaluates all legal actions (moves & switches)
    against the predicted optimal response of the opponent.
    """

    def _predict_opponent_moves(self, battle, opp, gen: int, sets_db: dict) -> list[Move]:
        """Predicts the opponent's moveset using revealed moves and database lookups.

        Returns a list of Move objects.
        """
        opp_moves = list(opp.moves.values()) if opp.moves else []
        move_objs = {m.id: m for m in opp_moves}

        clean_name = opp.species.lower().replace(" ", "").replace("-", "").replace("_", "")
        predicted_ids = sets_db.get(clean_name, {}).get("moves", [])

        # Supplement revealed moves with database predictions to have up to 4 moves
        for pid in predicted_ids:
            if pid not in move_objs:
                try:
                    move_objs[pid] = Move(pid, gen=gen)
                except Exception:
                    pass

        return list(move_objs.values())

    def _predict_opponent_best_switch_in(self, battle, me) -> Any:
        """Finds the opponent's best switch-in based on matchup scores."""
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
        """Static state evaluator from our perspective after a simulated turn.

        Args:
            my_action: Move object or Pokemon object (for switch).
            opp_action: Move object or "switch" string.
        """
        is_my_switch = not isinstance(my_action, Move)
        is_opp_switch = opp_action == "switch"

        # 1. BOTH PLAYERS SWITCH
        if is_my_switch and is_opp_switch:
            switch_in = my_action
            opp_switch_in = self._predict_opponent_best_switch_in(battle, me)
            if not opp_switch_in:
                opp_switch_in = opp

            me_hp_pct = switch_in.current_hp_fraction
            opp_hp_pct = opp_switch_in.current_hp_fraction
            matchup_score = self._estimate_matchup(switch_in, opp_switch_in, battle)

            # Utility based on remaining HP fractions and the resulting matchup
            return me_hp_pct - opp_hp_pct + 0.3 * matchup_score

        # 2. WE SWITCH, OPPONENT ATTACKS
        if is_my_switch and not is_opp_switch:
            switch_in = my_action
            opp_move = opp_action

            opp_dmg = 0.0
            if opp_move.base_power > 0 and opp_move.category in [MoveCategory.PHYSICAL, MoveCategory.SPECIAL]:
                _, opp_dmg = self._calculate_exact_damage_range(opp_move, opp, switch_in, battle)

            incoming_current_hp = switch_in.current_hp - opp_dmg
            me_hp_pct = max(0.0, incoming_current_hp / switch_in.max_hp) if switch_in.max_hp > 0 else 0.0
            opp_hp_pct = opp.current_hp_fraction
            matchup_score = self._estimate_matchup(switch_in, opp, battle)

            # Switching penalty is naturally handled by the damage taken on entry
            return me_hp_pct - opp_hp_pct + 0.3 * matchup_score

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

            me_hp_pct = me.current_hp_fraction
            opp_incoming_hp = opp_switch_in.current_hp - my_dmg
            opp_hp_pct = max(0.0, opp_incoming_hp / opp_switch_in.max_hp) if opp_switch_in.max_hp > 0 else 0.0
            matchup_score = self._estimate_matchup(opp_switch_in, me, battle)

            return me_hp_pct - opp_hp_pct - 0.3 * matchup_score

        # 4. BOTH ATTACK (Speed-aware sequential resolution)
        my_move = my_action
        opp_move = opp_action

        my_dmg = 0.0
        if my_move.base_power > 0 and my_move.category in [MoveCategory.PHYSICAL, MoveCategory.SPECIAL]:
            if not self._is_ability_immune(my_move, opp):
                _, my_dmg = self._calculate_exact_damage_range(my_move, me, opp, battle)

        opp_dmg = 0.0
        if opp_move.base_power > 0 and opp_move.category in [MoveCategory.PHYSICAL, MoveCategory.SPECIAL]:
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
                # Speed tie: assume opponent hits first to enforce risk-aversion
                my_hits_first = False

        if my_hits_first:
            # We hit first. Check if we KO the opponent
            opp_remaining_hp = opp.current_hp - my_dmg
            if opp_remaining_hp <= 0:
                opp_dmg = 0.0  # Opponent faints before moving
        else:
            # Opponent hits first. Check if they KO us
            me_remaining_hp = me.current_hp - opp_dmg
            if me_remaining_hp <= 0:
                my_dmg = 0.0  # We faint before moving

        # Calculate remaining HP fractions
        me_after_hp = max(0.0, (me.current_hp - opp_dmg) / me.max_hp) if me.max_hp > 0 else 0.0
        opp_after_hp = max(0.0, (opp.current_hp - my_dmg) / opp.max_hp) if opp.max_hp > 0 else 0.0

        # Apply a status move utility modifier if applicable
        status_bonus = 0.0
        if my_move.category == MoveCategory.STATUS and my_move.id in {"willowisp", "thunderwave", "toxic", "spore"}:
            if opp.status is None and not self._is_ability_immune(my_move, opp):
                status_bonus += 0.2

        if opp_move.category == MoveCategory.STATUS and opp_move.id in {"willowisp", "thunderwave", "toxic", "spore"}:
            if me.status is None and not self._is_ability_immune(opp_move, me):
                status_bonus -= 0.3

        # Risk-averse static evaluation (weighing damage taken 1.5x)
        return me_after_hp - 1.5 * opp_after_hp + status_bonus

    def _select_action(self, battle):
        btag = battle.battle_tag
        me = battle.active_pokemon
        opp = battle.opponent_active_pokemon

        # 1. Update roles and parse inferences
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

        # 2. Guaranteed KO — always take the KO immediately to save search overhead
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

        # 3. Minimax Adversarial Search (1-Ply)
        gen = self._get_gen(battle)
        sets_db = self._load_pokemon_sets(gen)

        # My legal actions
        my_actions = list(battle.available_moves) + list(battle.available_switches)
        if not my_actions:
            return self.choose_random_move(battle)

        # Opponent's predicted actions
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
                # If we have no opponent moves predicted, evaluate against a dummy "None" move
                score = self._evaluate_state_score(battle, my_action, None, me, opp, gen, sets_db)
                worst_case_score_for_this_action = score
            else:
                for opp_action in opp_actions:
                    score = self._evaluate_state_score(battle, my_action, opp_action, me, opp, gen, sets_db)

                    # Opponent wants to MINIMIZE our score
                    if score < worst_case_score_for_this_action:
                        worst_case_score_for_this_action = score

            # We want to MAXIMIZE our worst-case score
            if worst_case_score_for_this_action > best_worst_case_score:
                best_worst_case_score = worst_case_score_for_this_action
                best_action = my_action

        if best_action:
            if not isinstance(best_action, Move):
                # Switch action chosen
                return self.create_order(best_action)
            else:
                # Move action chosen
                self._record_used_move(btag, best_action.id)
                tera = self._should_terastallize(battle, best_action)
                return self.create_order(best_action, terastallize=tera)

        return self.choose_random_move(battle)
