"""Heuristic V3 — V2 logic with per-battle move tracking.

Same damage estimator and switching rules as V2, but records which
moves the agent uses in each battle for downstream analysis.
"""

from __future__ import annotations

from .v2 import HeuristicV2
from ..common import calculate_base_damage, get_speed, get_status_name


class HeuristicV3(HeuristicV2):
    """V2 damage + switching, plus per-battle move tracking."""

    @property
    def tracks_moves(self) -> bool:
        return True

    def _select_action(self, battle):
        me = battle.active_pokemon
        opp = battle.opponent_active_pokemon

        if me is None or opp is None:
            return None

        my_status = get_status_name(me)
        opp_status = get_status_name(opp)
        my_speed = get_speed(me, my_status)
        opp_speed = get_speed(opp, opp_status)

        best_move = None
        max_damage = -1.0
        if battle.available_moves:
            for move in battle.available_moves:
                dmg = calculate_base_damage(move, me, opp, my_status)
                if dmg > max_damage:
                    max_damage, best_move = dmg, move

        if battle.available_switches:
            if my_status == "TOX" and me.status_counter > 2:
                return self.create_order(battle.available_switches[0])
            if max_damage < 20 and my_speed < opp_speed:
                return self.create_order(battle.available_switches[0])

        if best_move:
            self._record_used_move(battle.battle_tag, best_move.id)
            return self.create_order(best_move)
        return None
