"""Heuristic V5 Doubles: Predictive KO and Efficiency.

The 'Apex' heuristic for doubles. V5 improves upon V4 by:
1. Joint KO Analysis: Calculates if the combined damage of both slots finishes an opponent.
2. Waste Mitigation: Penalizes targeting an opponent that is already being finished by the other slot.
3. Threat-Based Targeting: Prioritizes attacking opponents with higher offensive stats.
4. Selective Protect: Protect logic is now speed-aware (rarely protects if faster).
"""

from __future__ import annotations

import logging

from poke_env.player.battle_order import DoubleBattleOrder
from poke_env.battle.move import Move

from .v4 import HeuristicV4Doubles
from ..core.common import calculate_base_damage, get_status_name, get_stat

logger = logging.getLogger(__name__)

_OPP1 = 1
_OPP2 = 2

class HeuristicV5Doubles(HeuristicV4Doubles):
    """Predictive Synergy Heuristic."""

    @property
    def tracks_moves(self) -> bool:
        return False  # Removed move reuse penalty from V4

    def _score_pair(self, pair: DoubleBattleOrder, mon0, mon1, battle) -> float:
        """Core synergy logic for V8."""
        o0 = pair.first_order
        o1 = pair.second_order

        # 1. Base scores (V6 logic: Damage + Priority + Environment)
        s0 = self._score_order(o0, mon0, 0, battle) if mon0 else 0.0
        s1 = self._score_order(o1, mon1, 1, battle) if mon1 else 0.0
        
        total = s0 + s1

        # 2. Predictive KO and Focus Fire logic
        total += self._synergy_v5_decision(o0, o1, mon0, mon1, battle)
        
        # 3. Enhanced Protection Logic
        total += self._synergy_protect(o0, o1, mon0, mon1, battle)

        return total

    def _synergy_v5_decision(self, o0, o1, mon0, mon1, battle) -> float:
        """Evaluates focus fire vs waste mitigation."""
        if not (isinstance(o0.order, Move) and isinstance(o1.order, Move)):
            return 0.0
        
        opps = battle.opponent_active_pokemon
        if not any(opps):
            return 0.0

        move0, move1 = o0.order, o1.order
        t0, t1 = o0.move_target, o1.move_target
        
        # Calculate individual damages
        dmg0 = 0.0
        if t0 in [_OPP1, _OPP2] and opps[t0-1]:
            dmg0 = calculate_base_damage(move0, mon0, opps[t0-1], get_status_name(mon0))
        
        dmg1 = 0.0
        if t1 in [_OPP1, _OPP2] and opps[t1-1]:
            dmg1 = calculate_base_damage(move1, mon1, opps[t1-1], get_status_name(mon1))

        bonus = 0.0

        # Scenario: Targeting the SAME opponent
        if t0 == t1 and t0 in [_OPP1, _OPP2]:
            target = opps[t0-1]
            if target:
                hp = target.current_hp
                
                # Efficiency Check: Is one mon enough to KO?
                if dmg0 >= hp or dmg1 >= hp:
                    # Waste! One of these moves is redundant on this target.
                    # Unless both are spread moves, but we prioritize slot efficiency.
                    bonus -= 15.0 
                elif (dmg0 + dmg1) >= hp:
                    # Successful Synergy: Combined they KO! 
                    bonus += 70.0 
                else:
                    # Generic Focus Fire: Just solid pressure
                    bonus += 10.0

        # Scenario: Targeting DIFFERENT opponents
        elif t0 != t1 and t0 in [_OPP1, _OPP2] and t1 in [_OPP1, _OPP2]:
            target0, target1 = opps[t0-1], opps[t1-1]
            if target0 and target1:
                # Independent KO check
                if dmg0 >= target0.current_hp:
                    bonus += 40.0
                if dmg1 >= target1.current_hp:
                    bonus += 40.0
                
                # Target Threat Analysis: Prioritize high-threat targets
                threat0 = get_stat(target0, "atk") + get_stat(target0, "spa")
                threat1 = get_stat(target1, "atk") + get_stat(target1, "spa")
                
                # Bonus for attacking the scarier mon
                if threat0 > threat1:
                    bonus += 5.0
                else:
                    bonus -= 5.0 # (Slight penalty for targeting the 'safe' mon)

        return bonus

    def _synergy_protect(self, o0, o1, mon0, mon1, battle) -> float:
        """V8 Protect: Only protect if actually threatened and slower."""
        bonus = 0.0
        orders = [o0, o1]
        mons = [mon0, mon1]
        
        is_p = [self._is_protect(o.order) if isinstance(o.order, Move) else False for o in orders]
        
        if is_p[0] and is_p[1]:
            return -50.0 # Never double protect in V5

        opps = [o for o in battle.opponent_active_pokemon if o is not None]
        if not opps:
            return 0.0

        for i in range(2):
            if is_p[i] and mons[i]:
                # Speed Check: If I am faster than everyone, why protect?
                my_spe = get_stat(mons[i], "spe")
                opp_spe_max = max((get_stat(o, "spe") for o in opps), default=0)
                
                if my_spe > opp_spe_max:
                    bonus -= 30.0 # Strong penalty for 'fearful' protecting when fast
                
                # HP Check: Only protect if vulnerable
                if mons[i].current_hp_fraction < 0.35:
                    bonus += 40.0
                else:
                    bonus -= 10.0 # Don't protect full health mons for no reason
                    
        return bonus

    def _score_order(self, order, pokemon, slot, battle) -> float:
        """Clean base scoring (v3) without v4 repetition penalty."""
        # We skip v4 and go to v3 directly for the single-slot base
        from .v3 import HeuristicV3Doubles
        return HeuristicV3Doubles._score_order(self, order, pokemon, slot, battle)
