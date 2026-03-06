"""Safe 1-step lookahead player for Doubles.

Provides a robust baseline that selects moves based on a simple 1-turn 
damage projection for each active slot.
"""

from __future__ import annotations

from poke_env.battle.move_category import MoveCategory
from poke_env.player import Player
from poke_env.player.battle_order import DoubleBattleOrder


class SafeOneStepDoublesPlayer(Player):
    """Greedy 1-step lookahead for Doubles using base power and effectiveness."""

    def choose_move(self, battle):
        if not battle.active_pokemon:
            return self.choose_random_move(battle)

        # Separate orders by slot
        slot0_orders, slot1_orders = battle.valid_orders
        
        def score(single_order, pokemon):
            move = single_order.order
            if not hasattr(move, "base_power"): # Switch
                return -1.0
            if move.category == MoveCategory.STATUS:
                return 0.0
            
            bp = move.base_power or 0
            stab = 1.5 if move.type in pokemon.types else 1.0
            
            # Target identification
            target_idx = single_order.move_target
            opps = battle.opponent_active_pokemon
            
            if target_idx is None or target_idx <= 0: # Spread or no target
                living = [o for o in opps if o is not None and not o.fainted]
                eff = max((o.damage_multiplier(move) for o in living), default=1.0)
            else:
                idx = target_idx - 1
                if idx < len(opps) and opps[idx] is not None:
                    eff = opps[idx].damage_multiplier(move)
                else:
                    eff = 1.0
            
            acc = move.accuracy if move.accuracy is not None else 1.0
            return bp * stab * eff * acc

        # Select best for each slot
        best0 = max(slot0_orders, key=lambda o: score(o, battle.active_pokemon[0])) if len(battle.active_pokemon) > 0 else None
        best1 = max(slot1_orders, key=lambda o: score(o, battle.active_pokemon[1])) if len(battle.active_pokemon) > 1 else None

        # Join them safely (handles duplicate switches etc)
        valid_pairs = DoubleBattleOrder.join_orders(slot0_orders, slot1_orders)
        if not valid_pairs:
            return self.choose_random_doubles_move(battle)

        # In most cases, the max(score0 + score1) strategy works
        mon0 = battle.active_pokemon[0] if len(battle.active_pokemon) > 0 else None
        mon1 = battle.active_pokemon[1] if len(battle.active_pokemon) > 1 else None
        
        return max(
            valid_pairs,
            key=lambda p: (score(p.first_order, mon0) if mon0 else 0) + (score(p.second_order, mon1) if mon1 else 0)
        )
