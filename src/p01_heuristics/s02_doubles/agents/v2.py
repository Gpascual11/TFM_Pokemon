"""Heuristic V2 Doubles — stat-based damage with defensive switching.

Extends V1 by using actual attack/defence stats (with burn penalty) and
scoring switch orders positively when the current matchup is bad.
"""

from __future__ import annotations

from poke_env.player.battle_order import SingleBattleOrder
from poke_env.battle.move import Move
from poke_env.battle.pokemon import Pokemon as PokemonClass

from ..core.base import BaseHeuristic2v2
from ..core.common import calculate_base_damage, get_speed, get_status_name

_OPP1 = 1
_OPP2 = 2
_EMPTY = 0


class HeuristicV2Doubles(BaseHeuristic2v2):
    """Stat-based damage + willing-to-switch scoring per slot."""

    def _score_order(
        self, order: SingleBattleOrder, pokemon, slot: int, battle
    ) -> float:
        action = order.order
        my_status = get_status_name(pokemon)

        if isinstance(action, PokemonClass):
            return self._score_switch(action, pokemon, slot, battle, my_status)

        if not isinstance(action, Move):
            return -1.0

        target = order.move_target

        # Penalise ally-targeting orders
        if target < 0:
            return 0.0

        opps = battle.opponent_active_pokemon or []

        if target == _EMPTY:
            living = [o for o in opps if o is not None]
            return max(
                (calculate_base_damage(action, pokemon, o, my_status) for o in living),
                default=0.0,
            )
        else:
            idx = target - 1
            if idx < 0 or idx >= len(opps) or opps[idx] is None:
                return 0.0
            return calculate_base_damage(action, pokemon, opps[idx], my_status)

    def _score_switch(
        self, candidate, current_pokemon, slot, battle, my_status
    ) -> float:
        """Return a positive score when switching is beneficial, else very negative."""
        my_speed = get_speed(current_pokemon, my_status)
        opp_speeds = [
            get_speed(opp, get_status_name(opp))
            for opp in (battle.opponent_active_pokemon or [])
            if opp is not None
        ]
        min_opp_speed = min(opp_speeds) if opp_speeds else 0.0

        slot_moves = (
            battle.available_moves[slot] if slot < len(battle.available_moves) else []
        )
        opponents = [o for o in (battle.opponent_active_pokemon or []) if o is not None]
        max_my_damage = max(
            (
                calculate_base_damage(m, current_pokemon, opp, my_status)
                for m in slot_moves
                for opp in opponents
            ),
            default=0.0,
        )

        if my_status == "TOX" and current_pokemon.status_counter > 2:
            return self._switch_quality(candidate, battle)
        if max_my_damage < 20 and my_speed < min_opp_speed:
            return self._switch_quality(candidate, battle)
        return -10.0

    @staticmethod
    def _switch_quality(candidate, battle) -> float:
        opp_types = [
            t
            for opp in (battle.opponent_active_pokemon or [])
            if opp is not None
            for t in opp.types
        ]
        if not opp_types:
            return 0.0
        worst = max(candidate.damage_multiplier(t) for t in opp_types)
        return 4.0 - worst
