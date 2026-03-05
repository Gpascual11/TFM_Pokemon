import random
from typing import List, Tuple

from poke_env.environment.abstract_battle import AbstractBattle
from poke_env.environment.battle import Battle
from poke_env.environment.move import Move
from poke_env.environment.move_category import MoveCategory
from poke_env.environment.pokemon import Pokemon
from poke_env.environment.side_condition import SideCondition
from poke_env.player.player import Player

class TrueSimpleHeuristicsPlayer(Player):
    ENTRY_HAZARDS = {
        "spikes": SideCondition.SPIKES,
        "stealhrock": SideCondition.STEALTH_ROCK,
        "stickyweb": SideCondition.STICKY_WEB,
        "toxicspikes": SideCondition.TOXIC_SPIKES,
    }
    ANTI_HAZARDS_MOVES = {"rapidspin", "defog"}
    SPEED_TIER_COEFICIENT = 0.1
    HP_FRACTION_COEFICIENT = 0.4
    SWITCH_OUT_MATCHUP_THRESHOLD = -2

    def _estimate_matchup(self, mon: Pokemon, opponent: Pokemon):
        score = max([opponent.damage_multiplier(t) for t in mon.types if t is not None])
        score -= max([mon.damage_multiplier(t) for t in opponent.types if t is not None])
        if mon.base_stats["spe"] > opponent.base_stats["spe"]:
            score += self.SPEED_TIER_COEFICIENT
        elif opponent.base_stats["spe"] > mon.base_stats["spe"]:
            score -= self.SPEED_TIER_COEFICIENT
        score += mon.current_hp_fraction * self.HP_FRACTION_COEFICIENT
        score -= opponent.current_hp_fraction * self.HP_FRACTION_COEFICIENT
        return score

    def _should_dynamax(self, battle: AbstractBattle, n_remaining_mons: int):
        if battle.can_dynamax:
            if len([m for m in battle.team.values() if m.current_hp_fraction == 1]) == 1 and battle.active_pokemon.current_hp_fraction == 1:
                return True
            if self._estimate_matchup(battle.active_pokemon, battle.opponent_active_pokemon) > 0 and battle.active_pokemon.current_hp_fraction == 1 and battle.opponent_active_pokemon.current_hp_fraction == 1:
                return True
            if n_remaining_mons == 1:
                return True
        return False

    def _should_terastallize(self, battle: Battle, move: Move) -> bool:
        active = battle.active_pokemon
        opp_active = battle.opponent_active_pokemon
        if not getattr(battle, "can_tera", False) or not active or not opp_active or active.tera_type is None:
            return False
        offensive_tera_score = opp_active.damage_multiplier(move.type)
        defensive_score = min([1 / (active.damage_multiplier(t) or 1 / 8) for t in opp_active.types])
        defensive_tera_score = min([1 / (t.damage_multiplier(active.tera_type, type_chart=active._data.type_chart) or 1 / 8) for t in opp_active.types])
        return offensive_tera_score * (defensive_tera_score / defensive_score) > 1

    def _should_switch_out(self, battle: AbstractBattle):
        active = battle.active_pokemon
        opponent = battle.opponent_active_pokemon
        if [m for m in battle.available_switches if self._estimate_matchup(m, opponent) > 0]:
            if active.boosts.get("def", 0) <= -3 or active.boosts.get("spd", 0) <= -3:
                return True
            if active.boosts.get("atk", 0) <= -3 and active.stats.get("atk", 0) >= active.stats.get("spa", 0):
                return True
            if active.boosts.get("spa", 0) <= -3 and active.stats.get("atk", 0) <= active.stats.get("spa", 0):
                return True
            if self._estimate_matchup(active, opponent) < self.SWITCH_OUT_MATCHUP_THRESHOLD:
                return True
        return False

    def _stat_estimation(self, mon: Pokemon, stat: str):
        if mon.boosts.get(stat, 0) > 1:
            boost = (2 + mon.boosts[stat]) / 2
        else:
            boost = 2 / (2 - mon.boosts.get(stat, 0))
        return ((2 * mon.base_stats.get(stat, 100) + 31) + 5) * boost

    def choose_move(self, battle: AbstractBattle):
        active = battle.active_pokemon
        opponent = battle.opponent_active_pokemon

        if active is None or opponent is None:
            return self.choose_random_move(battle)

        physical_ratio = self._stat_estimation(active, "atk") / self._stat_estimation(opponent, "def")
        special_ratio = self._stat_estimation(active, "spa") / self._stat_estimation(opponent, "spd")

        if battle.available_moves and (not self._should_switch_out(battle) or not battle.available_switches):
            n_remaining_mons = len([m for m in battle.team.values() if m.fainted is False])
            n_opp_remaining_mons = 6 - len([m for m in battle.opponent_team.values() if m.fainted is True])

            for move in battle.available_moves:
                if n_opp_remaining_mons >= 3 and move.id in self.ENTRY_HAZARDS and self.ENTRY_HAZARDS[move.id] not in battle.opponent_side_conditions:
                    return self.create_order(move)
                elif battle.side_conditions and move.id in self.ANTI_HAZARDS_MOVES and n_remaining_mons >= 2:
                    return self.create_order(move)

            if active.current_hp_fraction == 1 and self._estimate_matchup(active, opponent) > 0:
                for move in battle.available_moves:
                    if move.boosts and sum(move.boosts.values()) >= 2 and move.target == "self" and min([active.boosts.get(s, 0) for s, v in move.boosts.items() if v > 0]) < 6:
                        return self.create_order(move)

            move, score = max(
                [(m, m.base_power * (1.5 if m.type in active.types else 1) * (physical_ratio if m.category == MoveCategory.PHYSICAL else special_ratio) * m.accuracy * m.expected_hits * opponent.damage_multiplier(m)) for m in battle.available_moves],
                key=lambda x: x[1]
            )
            
            try:
                if getattr(battle, "can_tera", False):
                    return self.create_order(move, dynamax=self._should_dynamax(battle, n_remaining_mons), terastallize=self._should_terastallize(battle, move))
            except:
                pass
                
            return self.create_order(move, dynamax=self._should_dynamax(battle, n_remaining_mons))

        if battle.available_switches:
            switches = battle.available_switches
            return self.create_order(max(switches, key=lambda s: self._estimate_matchup(s, opponent)))

        return self.choose_random_move(battle)
