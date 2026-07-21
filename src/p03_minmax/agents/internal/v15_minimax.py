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


class HeuristicV15Minimax(HeuristicV14):
    """1-Ply Adversarial Minimax Agent using Heuristic V14 Evaluator & Showdown DB.

    This agent extends HeuristicV14 to perform a 1-ply adversarial lookahead
    over the current turn. It evaluates all legal actions (moves & switches)
    against the predicted optimal response of the opponent.
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
        """Predicts the opponent's moveset using revealed moves and risk-weighted database lookups.

        Returns a list of Move objects.
        """
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
        """Enhanced static state evaluator with unified risk-averse leaf value tuning."""
        is_my_switch = not isinstance(my_action, Move)
        is_opp_switch = opp_action == "switch"

        # Guard: no opponent move predicted (empty moveset + no bench)
        if opp_action is None:
            me_hp = my_action.current_hp_fraction if is_my_switch else me.current_hp_fraction
            return me_hp - 1.5 * opp.current_hp_fraction

        # Base current matchup before simulated turn
        current_matchup = self._estimate_matchup(me, opp, battle) if me and opp else 0.0

        # 1. BOTH PLAYERS SWITCH
        if is_my_switch and is_opp_switch:
            switch_in = my_action
            opp_switch_in = self._predict_opponent_best_switch_in(battle, me) or opp
            me_hp_pct = switch_in.current_hp_fraction
            opp_hp_pct = opp_switch_in.current_hp_fraction
            matchup_score = self._estimate_matchup(switch_in, opp_switch_in, battle)
            return me_hp_pct - 1.5 * opp_hp_pct + 0.35 * matchup_score

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

            # Tactical escape bonus: rewarding pivoting out of a terrible active matchup
            escape_bonus = 0.20 if current_matchup < -0.3 and matchup_score > 0.1 else 0.0

            return me_hp_pct - 1.5 * opp_hp_pct + 0.35 * matchup_score + escape_bonus

        # 3. WE ATTACK, OPPONENT SWITCHES
        if not is_my_switch and is_opp_switch:
            my_move = my_action
            opp_switch_in = self._predict_opponent_best_switch_in(battle, me) or opp
            my_dmg = 0.0
            if my_move.base_power > 0 and my_move.category in [MoveCategory.PHYSICAL, MoveCategory.SPECIAL]:
                if not self._is_ability_immune(my_move, opp_switch_in):
                    _, my_dmg = self._calculate_exact_damage_range(my_move, me, opp_switch_in, battle)

            me_hp_pct = me.current_hp_fraction
            opp_incoming_hp = opp_switch_in.current_hp - my_dmg
            opp_hp_pct = max(0.0, opp_incoming_hp / opp_switch_in.max_hp) if opp_switch_in.max_hp > 0 else 0.0
            matchup_score = self._estimate_matchup(opp_switch_in, me, battle)

            return me_hp_pct - 1.5 * opp_hp_pct - 0.35 * matchup_score

        # 4. BOTH ATTACK (Speed-aware sequential resolution)
        my_move = my_action
        opp_move = opp_action

        # Check for Protect / Detect / Spiky Shield / Baneful Bunker / King's Shield
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
                my_hits_first = False  # Risk-averse speed tie assumption

        me_faints_first = False
        opp_faints_first = False
        if my_hits_first:
            opp_remaining_hp = opp.current_hp - my_dmg
            if opp_remaining_hp <= 0:
                opp_dmg = 0.0  # Opponent faints before moving
                opp_faints_first = True
        else:
            me_remaining_hp = me.current_hp - opp_dmg
            if me_remaining_hp <= 0:
                my_dmg = 0.0  # We faint before moving
                me_faints_first = True

        # Healing / Recovery bonus (only if we didn't faint before our turn executed!)
        healing_bonus = 0.0
        if not me_faints_first:
            if my_move.id in {"roost", "recover", "synthesis", "moonlight", "softboiled", "slackoff", "strengthsap", "shoreup"}:
                if me.current_hp_fraction < 0.85:
                    healing_bonus += min(0.50, 1.0 - me.current_hp_fraction)
            elif my_move.id in {"gigadrain", "drainpunch", "hornleech", "paraboliccharge", "bitterblade", "matchagotcha", "drainingkiss", "oblivionwing"}:
                if me.max_hp > 0:
                    healing_bonus += min(0.50, 0.5 * (my_dmg / me.max_hp))

        # Calculate remaining HP fractions after simulated turn
        me_after_hp = max(0.0, min(1.0, (me.current_hp - opp_dmg) / me.max_hp + healing_bonus)) if me.max_hp > 0 else 0.0
        opp_after_hp = max(0.0, (opp.current_hp - my_dmg) / opp.max_hp) if opp.max_hp > 0 else 0.0

        status_bonus = 0.0
        boost_bonus = 0.0
        hazard_bonus = 0.0

        if not me_faints_first:
            # Status condition utility modifier
            if my_move.category == MoveCategory.STATUS and my_move.id in {"willowisp", "thunderwave", "toxic", "spore", "yawn"}:
                if opp.status is None and not self._is_ability_immune(my_move, opp) and not opp_protects:
                    status_bonus += 0.22

            # Stat setup / boost moves utility modifier
            if my_move.category == MoveCategory.STATUS and me_after_hp > 0.45:
                if my_move.id in {"swordsdance", "nastyplot", "quiverdance", "dragondance", "shellsmash", "irondefense", "calmmind"}:
                    boost_bonus += 0.24 * me_after_hp

            # Hazard setting and clearing utility modifier
            if my_move.id in {"stealthrock", "spikes", "toxicspikes", "stickyweb"}:
                if sum(battle.opponent_side_conditions.values()) < 2 and len(battle.opponent_team) > 1:
                    hazard_bonus += 0.18
            elif my_move.id in {"defog", "rapidspin", "mortalspin"}:
                if len(battle.side_conditions) > 0:
                    hazard_bonus += 0.20

        if not opp_faints_first and not my_protects:
            if opp_move.category == MoveCategory.STATUS and opp_move.id in {"willowisp", "thunderwave", "toxic", "spore", "yawn"}:
                if me.status is None and not self._is_ability_immune(opp_move, me):
                    status_bonus -= 0.25

        # Speed initiative and momentum bonus
        momentum_bonus = 0.05 if my_speed > opp_speed else 0.0

        # Risk-averse static evaluation across all actions
        return me_after_hp - 1.5 * opp_after_hp + status_bonus + boost_bonus + hazard_bonus + momentum_bonus

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

        endgame_order = self._run_endgame_solver(battle, me, opp)
        if endgame_order:
            self._endgame_solves_by_battle[btag] = self._endgame_solves_by_battle.get(btag, 0) + 1
            return endgame_order

        # 3. Minimax Adversarial Search (1-Ply)
        gen = self._get_gen(battle)
        sets_db = self._load_pokemon_sets(gen)

        # My legal actions
        my_actions: list[Any] = list(battle.available_moves)
        if battle.available_switches and opp:
            for switch_cand in battle.available_switches:
                if self._is_switch_allowed(battle, switch_cand):
                    my_actions.append(switch_cand)
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
                # Switch action chosen
                self._search_switches_by_battle[btag] = self._search_switches_by_battle.get(btag, 0) + 1
                actual_order = self.create_order(best_action)
            else:
                # Move action chosen
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
