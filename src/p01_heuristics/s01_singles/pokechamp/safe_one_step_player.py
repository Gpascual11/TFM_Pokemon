"""Safe 1-step lookahead player that avoids pokechamp's LocalSim/prompts path.

OneStepPlayer in pokechamp uses LocalSim + get_number_turns_faint / get_status_num_turns_fnt
from pokechamp.prompts, which can hang when gen9 pokedex or moves-set JSON are missing
(empty cache). This module provides a drop-in replacement that uses only poke_env types
and a simple damage estimate: base_power * STAB * type effectiveness * accuracy,
so no heavy or blocking code paths.
"""

from __future__ import annotations

from poke_env.environment.abstract_battle import AbstractBattle
from poke_env.environment.move_category import MoveCategory
from poke_env.player import Player


class SafeOneStepPlayer(Player):
    """1-step lookahead player using only poke_env damage scoring (no LocalSim/prompts)."""

    def choose_move(self, battle: AbstractBattle):
        if not battle.available_moves or battle.active_pokemon.fainted:
            return self.choose_random_move(battle)
        active = battle.active_pokemon
        opp = battle.opponent_active_pokemon
        if opp is None or opp.fainted:
            return self.choose_random_move(battle)

        def score(move):
            if move.category == MoveCategory.STATUS:
                return -1.0  # Prefer damaging moves when we want to KO
            bp = move.base_power or 0
            stab = 1.5 if move.type and move.type in active.types else 1.0
            try:
                eff = opp.damage_multiplier(move) if move.type else 1.0
            except Exception:
                eff = 1.0
            acc = move.accuracy if move.accuracy is not None else 1.0
            return bp * stab * eff * acc

        damaging = [m for m in battle.available_moves if m.category != MoveCategory.STATUS]
        if not damaging:
            return self.choose_random_move(battle)
        best_move = max(damaging, key=score)
        return self.create_order(best_move)
