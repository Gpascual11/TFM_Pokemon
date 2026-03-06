"""Abyssal Bot baseline for Doubles.

Ported from the pokechamp repository and adapted for Gen 9 Doubles 
using standard poke-env structures.
"""

from __future__ import annotations

import logging
import random
from typing import List, Optional, Union

logger = logging.getLogger(__name__)

from poke_env.battle.abstract_battle import AbstractBattle
from poke_env.battle.battle import Battle
from poke_env.battle.double_battle import DoubleBattle
from poke_env.battle.move import Move
from poke_env.battle.move_category import MoveCategory
from poke_env.battle.pokemon import Pokemon
from poke_env.battle.side_condition import SideCondition
from poke_env.player.player import Player
from poke_env.player.battle_order import DoubleBattleOrder, BattleOrder, PassBattleOrder


class AbyssalPlayer(Player):
    ENTRY_HAZARDS = {
        "spikes": SideCondition.SPIKES,
        "stealthrock": SideCondition.STEALTH_ROCK,
        "stickyweb": SideCondition.STICKY_WEB,
        "toxicspikes": SideCondition.TOXIC_SPIKES,
    }

    ANTI_HAZARDS_MOVES = {"rapidspin", "defog"}

    SPEED_TIER_COEFICIENT = 0.1
    HP_FRACTION_COEFICIENT = 0.4
    SWITCH_OUT_MATCHUP_THRESHOLD = -2

    def _estimate_matchup(self, mon: Pokemon, opponent: Pokemon):
        if not mon or not opponent:
            return 0
        
        score = max([opponent.damage_multiplier(t) for t in mon.types if t is not None], default=1.0)
        score -= max(
            [mon.damage_multiplier(t) for t in opponent.types if t is not None], default=1.0
        )
        if mon.base_stats["spe"] > opponent.base_stats["spe"]:
            score += self.SPEED_TIER_COEFICIENT
        elif opponent.base_stats["spe"] > mon.base_stats["spe"]:
            score -= self.SPEED_TIER_COEFICIENT

        score += mon.current_hp_fraction * self.HP_FRACTION_COEFICIENT
        score -= opponent.current_hp_fraction * self.HP_FRACTION_COEFICIENT

        return score

    def _should_switch_out(self, battle: AbstractBattle):
        active = battle.active_pokemon
        opponent = battle.opponent_active_pokemon
        
        if isinstance(active, list): # Handles doubles active list if passed
             # Simplified for now: just look at the first one
             if not active or not active[0]: return False
             active = active[0]
        
        if opponent is None or (isinstance(opponent, list) and (not opponent or not opponent[0])):
            return False
            
        if isinstance(opponent, list):
            opponent = opponent[0]

        # If there is a decent switch in...
        if [
            m
            for m in battle.available_switches
            if self._estimate_matchup(m, opponent) > 0
        ]:
            # ...and a 'good' reason to switch out
            if active.boosts["def"] <= -3 or active.boosts["spd"] <= -3:
                return True
            if (
                active.boosts["atk"] <= -3
                and active.stats["atk"] >= active.stats["spa"]
            ):
                return True
            if (
                active.boosts["spa"] <= -3
                and active.stats["atk"] <= active.stats["spa"]
            ):
                return True
            if (
                self._estimate_matchup(active, opponent)
                < self.SWITCH_OUT_MATCHUP_THRESHOLD
            ):
                return True
        return False

    def _stat_estimation(self, mon: Pokemon, stat: str):
        # Stats boosts value
        if mon.boosts[stat] > 1:
            boost = (2 + mon.boosts[stat]) / 2
        else:
            boost = 2 / (2 - mon.boosts[stat])
        return ((2 * mon.base_stats[stat] + 31) + 5) * boost

    def choose_move(self, battle: AbstractBattle):
        if isinstance(battle, DoubleBattle):
            return self._choose_abyssal_doubles_move(battle)

        # Main mons shortcuts
        active = battle.active_pokemon
        opponent = battle.opponent_active_pokemon

        if not active or not opponent:
            return self.choose_random_move(battle)

        # Rough estimation of damage ratio
        physical_ratio = self._stat_estimation(active, "atk") / max(self._stat_estimation(
            opponent, "def"
        ), 1)
        special_ratio = self._stat_estimation(active, "spa") / max(self._stat_estimation(
            opponent, "spd"
        ), 1)

        next_action = None
        if battle.available_moves and (
            not self._should_switch_out(battle) or not battle.available_switches
        ):
            n_opp_remaining_mons = 6 - len(
                [m for m in battle.opponent_team.values() if m.fainted is True]
            )

            # Entry hazard...
            for move in battle.available_moves:
                # ...setup
                if (
                    n_opp_remaining_mons >= 3
                    and move.id in self.ENTRY_HAZARDS
                    and self.ENTRY_HAZARDS[move.id]
                    not in battle.opponent_side_conditions
                ):
                    next_action = self.create_order(move)
                    break

            if next_action is None:
                move = max(
                    battle.available_moves,
                    key=lambda m: (m.base_power or 0)
                    * (1.5 if m.type in active.types else 1)
                    * (
                        physical_ratio
                        if m.category == MoveCategory.PHYSICAL
                        else special_ratio
                    )
                    * (m.accuracy or 1.0)
                    * (m.expected_hits or 1.0)
                    * opponent.damage_multiplier(m),
                )
                next_action = self.create_order(move)

        if next_action is None and battle.available_switches:
            switches: List[Pokemon] = battle.available_switches
            next_action = self.create_order(
                max(
                    switches,
                    key=lambda s: self._estimate_matchup(s, opponent),
                )
            )

        return next_action if next_action else self.choose_random_move(battle)

    def _choose_abyssal_doubles_move(self, battle: DoubleBattle):
        """Double battle implementation for AbyssalPlayer."""
        logger.info(f"Abyssal choosing move for turn {battle.turn}")
        orders = [None, None]
        
        # Handle force switch cases properly
        if any(battle.force_switch):
            for i in range(2):
                if battle.force_switch[i]:
                    if battle.available_switches[i]:
                        opp = battle.opponent_active_pokemon[0] or battle.opponent_active_pokemon[1]
                        best_switch = max(
                            battle.available_switches[i],
                            key=lambda s: self._estimate_matchup(s, opp) if opp else 0
                        )
                        orders[i] = self.create_order(best_switch)
                else:
                    orders[i] = None
            return DoubleBattleOrder(
                first_order=orders[0] or PassBattleOrder(), 
                second_order=orders[1] or PassBattleOrder()
            )
        
        # Normal battle logic 
        for i in range(2):
            if battle.active_pokemon[i] is None or battle.active_pokemon[i].fainted:
                if battle.available_switches[i]:
                    opp = battle.opponent_active_pokemon[0] or battle.opponent_active_pokemon[1]
                    best_switch = max(
                        battle.available_switches[i],
                        key=lambda s: self._estimate_matchup(s, opp) if opp else 0
                    )
                    orders[i] = self.create_order(best_switch)
                continue
            
            active = battle.active_pokemon[i]
            opp_active = [o for o in battle.opponent_active_pokemon if o and not o.fainted]
            
            # Simplified switch out logic for doubles
            if (battle.available_switches[i] and opp_active and
                self._estimate_matchup(active, opp_active[0]) < self.SWITCH_OUT_MATCHUP_THRESHOLD):
                best_switch = max(
                    battle.available_switches[i],
                    key=lambda s: self._estimate_matchup(s, opp_active[0])
                )
                orders[i] = self.create_order(best_switch)
                continue
            
            # Choose best move with target selection
            if battle.available_moves[i]:
                best_move = None
                best_score = -float('inf')
                best_target = 1
                
                for move in battle.available_moves[i]:
                    move_power = (move.base_power or 0)
                    if move.target in ["allAdjacentFoes", "allAdjacent"]:
                        move_power *= 1.5
                    
                    for target_idx, opp in enumerate(battle.opponent_active_pokemon):
                        if opp is None or opp.fainted:
                            continue
                        
                        target = target_idx + 1
                        type_multiplier = opp.damage_multiplier(move) if move.type else 1.0
                        stab_bonus = 1.5 if move.type in active.types else 1.0
                        
                        try:
                            if move.category == MoveCategory.PHYSICAL:
                                active_atk = active.stats.get("atk") or active.base_stats.get("atk") or 100
                                opp_def = opp.stats.get("def") or opp.base_stats.get("def") or 100
                                power_ratio = active_atk / max(opp_def, 1)
                            elif move.category == MoveCategory.SPECIAL:
                                active_spa = active.stats.get("spa") or active.base_stats.get("spa") or 100
                                opp_spd = opp.stats.get("spd") or opp.base_stats.get("spd") or 100
                                power_ratio = active_spa / max(opp_spd, 1)
                            else:
                                power_ratio = 1.0
                        except (KeyError, AttributeError, TypeError):
                            power_ratio = 1.0
                        
                        score = (move_power * type_multiplier * stab_bonus * 
                                power_ratio * (move.accuracy or 1.0) * (move.expected_hits or 1.0))
                        
                        if score > best_score:
                            best_score = score
                            best_move = move
                            best_target = target
                
                if best_move:
                    orders[i] = self.create_order(best_move, move_target=best_target)
                else:
                    orders[i] = self.create_order(random.choice(battle.available_moves[i]), move_target=1)
            elif battle.available_switches[i]:
                opp = opp_active[0] if opp_active else None
                best_switch = max(
                    battle.available_switches[i],
                    key=lambda s: self._estimate_matchup(s, opp) if opp else 0
                )
                orders[i] = self.create_order(best_switch)
        
        return DoubleBattleOrder(
            first_order=orders[0] or PassBattleOrder(), 
            second_order=orders[1] or PassBattleOrder()
        )
