"""Heuristic V2 — stats-based damage with defensive switching.

Extends V1 by using actual attack/defence stats (with burn penalty)
and introducing two switching triggers:

* Badly poisoned for several turns → switch to reset toxic counter.
* Best available move is weak *and* we are outsped → pivot out.
"""

from __future__ import annotations

from ...core.base import BaseHeuristic1v1
from ...core.common import calculate_base_damage, get_speed, get_status_name


class HeuristicV2(BaseHeuristic1v1):
    """Enhanced version of V1 with basic defensive switching.
    
    V2 introduces the shared damage estimator and two simple pivot rules:
    escape stacking Toxic damage and switch out when our best move is weak
    and we are outsped.
    """

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
            return self.create_order(best_move)
        return None
