"""Heuristic V7: Strategic Battler with Matchup Awareness.

Combines field-aware damage (V5 style) with Abyssal's strategic framework:

- **Matchup-Based Switching**: Evaluates type advantage scores to pick optimal switch-ins.
- **Hazard Awareness**: Sets entry hazards (Stealth Rock, Spikes, etc.) and removes them.
- **Setup Move Usage**: Uses boost moves when at full HP with a positive matchup.
- **KO Priority**: Pre-checks for guaranteed knockouts (priority moves first).
- **Complete Damage Formula**: Stat-boost-aware × accuracy × expected_hits × field mods.
"""

from __future__ import annotations

from poke_env.environment.move_category import MoveCategory
from poke_env.environment.side_condition import SideCondition

from ...core.base import BaseHeuristic1v1
from ...core.common import get_status_name


ENTRY_HAZARDS = {
    "spikes": SideCondition.SPIKES,
    "stealthrock": SideCondition.STEALTH_ROCK,
    "stickyweb": SideCondition.STICKY_WEB,
    "toxicspikes": SideCondition.TOXIC_SPIKES,
}
ANTI_HAZARDS_MOVES = {"rapidspin", "defog"}

SPEED_TIER_COEFF = 0.1
HP_FRACTION_COEFF = 0.4
SWITCH_OUT_MATCHUP_THRESHOLD = -2


class HeuristicV7(BaseHeuristic1v1):
    """Strategic heuristic with matchup switching, hazards, and setup moves."""

    @property
    def tracks_moves(self) -> bool:
        return True

    # -- Template hooks ---------------------------------------------------

    def _pre_move_hook(self, battle):
        """Short-circuit with a guaranteed KO move (priority moves first)."""
        me = battle.active_pokemon
        opp = battle.opponent_active_pokemon

        if not battle.available_moves or me is None or opp is None:
            return None

        opp_hp_fraction = opp.current_hp_fraction
        if opp_hp_fraction <= 0:
            return None

        sorted_moves = sorted(
            battle.available_moves,
            key=lambda m: m.entry.get("priority", 0),
            reverse=True,
        )
        for move in sorted_moves:
            dmg_fraction = self._estimate_damage_fraction(move, me, opp, battle)
            if dmg_fraction >= opp_hp_fraction:
                btag = battle.battle_tag
                self._ko_checks_by_battle[btag] = self._ko_checks_by_battle.get(btag, 0) + 1
                self._record_used_move(btag, move.id)
                return self.create_order(move)

        return None

    def _select_action(self, battle):
        me = battle.active_pokemon
        opp = battle.opponent_active_pokemon

        if me is None or opp is None:
            return None

        # -- Phase 1: Hazard Logic --
        hazard_order = self._hazard_logic(battle, me, opp)
        if hazard_order:
            return hazard_order

        # -- Phase 2: Setup Logic --
        setup_order = self._setup_logic(battle, me, opp)
        if setup_order:
            return setup_order

        # -- Phase 3: Switch Check --
        if battle.available_switches and self._should_switch_out(battle, me, opp):
            switch = self._get_best_switch(battle)
            if switch:
                btag = battle.battle_tag
                self._matchup_switches_by_battle[btag] = self._matchup_switches_by_battle.get(btag, 0) + 1
                return self.create_order(switch)

        # -- Phase 4: Best Move --
        best_move = None
        max_score = -1.0
        for move in battle.available_moves or []:
            score = self._score_move(move, me, opp, battle)
            if score > max_score:
                max_score, best_move = score, move

        if best_move:
            self._record_used_move(battle.battle_tag, best_move.id)
            return self.create_order(best_move)

        return None

    # -- Hazard Logic -----------------------------------------------------

    def _hazard_logic(self, battle, me, opp):
        """Set entry hazards or remove own side hazards."""
        if not battle.available_moves:
            return None

        btag = battle.battle_tag
        n_opp_remaining = 6 - len([m for m in battle.opponent_team.values() if m.fainted])
        n_remaining = len([m for m in battle.team.values() if not m.fainted])

        # Set hazards if opponent has 3+ pokemon and hazard not already up
        if n_opp_remaining >= 3:
            for move in battle.available_moves:
                if move.id in ENTRY_HAZARDS:
                    condition = ENTRY_HAZARDS[move.id]
                    if condition not in battle.opponent_side_conditions:
                        self._hazard_sets_by_battle[btag] = self._hazard_sets_by_battle.get(btag, 0) + 1
                        self._record_used_move(btag, move.id)
                        return self.create_order(move)

        # Remove own hazards if we have 2+ pokemon alive
        if battle.side_conditions and n_remaining >= 2:
            for move in battle.available_moves:
                if move.id in ANTI_HAZARDS_MOVES:
                    self._hazard_removals_by_battle[btag] = self._hazard_removals_by_battle.get(btag, 0) + 1
                    self._record_used_move(btag, move.id)
                    return self.create_order(move)

        return None

    # -- Setup Logic ------------------------------------------------------

    def _setup_logic(self, battle, me, opp):
        """Use boost moves when safe: full HP + positive matchup."""
        if me.current_hp_fraction < 1.0:
            return None

        if self._estimate_matchup(me, opp) <= 0:
            return None

        for move in battle.available_moves or []:
            if not move.boosts:
                continue
            if move.target != "self":
                continue
            boost_sum = sum(v for v in move.boosts.values() if v > 0)
            if boost_sum < 2:
                continue
            min_current = min(
                me.boosts.get(s, 0) for s, v in move.boosts.items() if v > 0
            )
            if min_current >= 6:
                continue
            btag = battle.battle_tag
            self._setup_uses_by_battle[btag] = self._setup_uses_by_battle.get(btag, 0) + 1
            self._record_used_move(btag, move.id)
            return self.create_order(move)

        return None

    # -- Switching --------------------------------------------------------

    def _should_switch_out(self, battle, me, opp) -> bool:
        """Switch if matchup is bad or stats are severely dropped."""
        if not [s for s in battle.available_switches if self._estimate_matchup(s, opp) > 0]:
            return False

        if me.boosts.get("def", 0) <= -3 or me.boosts.get("spd", 0) <= -3:
            return True

        me_stats = me.stats or me.base_stats or {}
        if me.boosts.get("atk", 0) <= -3 and me_stats.get("atk", 0) >= me_stats.get("spa", 0):
            return True
        if me.boosts.get("spa", 0) <= -3 and me_stats.get("atk", 0) <= me_stats.get("spa", 0):
            return True

        if self._estimate_matchup(me, opp) < SWITCH_OUT_MATCHUP_THRESHOLD:
            return True

        return False

    def _get_best_switch(self, battle):
        """Pick the teammate with the best matchup against the opponent."""
        opp = battle.opponent_active_pokemon
        if opp is None:
            return None

        return max(
            battle.available_switches,
            key=lambda s: self._estimate_matchup(s, opp),
        )

    # -- Matchup Estimation -----------------------------------------------

    @staticmethod
    def _estimate_matchup(mon, opponent) -> float:
        """Evaluate how favorable a Pokemon is against an opponent.

        Considers type matchup (offensive + defensive), speed tier, and HP.
        """
        mon_types = [t for t in mon.types if t is not None]
        opp_types = [t for t in opponent.types if t is not None]

        if not mon_types or not opp_types:
            return 0.0

        score = max(opponent.damage_multiplier(t) for t in mon_types)
        score -= max(mon.damage_multiplier(t) for t in opp_types)

        mon_speed = mon.base_stats.get("spe", 100) if mon.base_stats else 100
        opp_speed = opponent.base_stats.get("spe", 100) if opponent.base_stats else 100
        if mon_speed > opp_speed:
            score += SPEED_TIER_COEFF
        elif opp_speed > mon_speed:
            score -= SPEED_TIER_COEFF

        score += mon.current_hp_fraction * HP_FRACTION_COEFF
        score -= opponent.current_hp_fraction * HP_FRACTION_COEFF

        return score

    # -- Damage Estimation ------------------------------------------------

    @staticmethod
    def _get_boosted_stat(pokemon, stat_name: str) -> float:
        """Calculate a stat with in-battle stage boosts applied."""
        raw_stat = 100
        if pokemon.stats and pokemon.stats.get(stat_name):
            raw_stat = pokemon.stats[stat_name]
        elif pokemon.base_stats and pokemon.base_stats.get(stat_name):
            raw_stat = pokemon.base_stats[stat_name]

        boost = pokemon.boosts.get(stat_name, 0)
        if boost > 0:
            multiplier = (2.0 + boost) / 2.0
        elif boost < 0:
            multiplier = 2.0 / (2.0 - boost)
        else:
            multiplier = 1.0

        return raw_stat * multiplier

    def _estimate_damage_fraction(self, move, attacker, defender, battle) -> float:
        """Estimate damage as a fraction of defender's max HP (0.0 to 1.0+).

        Uses a calibrated formula so the KO check in _pre_move_hook is reliable.
        """
        if move.base_power <= 1:
            return 0.0

        if move.category == MoveCategory.PHYSICAL:
            atk = self._get_boosted_stat(attacker, "atk")
            defe = self._get_boosted_stat(defender, "def")
            if get_status_name(attacker) == "BRN":
                atk *= 0.5
        elif move.category == MoveCategory.SPECIAL:
            atk = self._get_boosted_stat(attacker, "spa")
            defe = self._get_boosted_stat(defender, "spd")
        else:
            return 0.0

        defe = max(defe, 1.0)

        effectiveness = defender.damage_multiplier(move)
        stab = 1.5 if move.type in attacker.types else 1.0
        expected_hits = move.expected_hits if hasattr(move, "expected_hits") else 1.0

        # Simplified damage formula calibrated to HP fraction
        # Level 80 approximation for random battles: ((2*80/5+2) * bp * atk/def) / 50 + 2) / max_hp
        # Simplified to proportional: (0.44 * bp * atk/def * stab * eff) / defender_hp_stat
        defender_hp = defender.max_hp if hasattr(defender, "max_hp") and defender.max_hp else 300
        raw_damage = (0.44 * move.base_power * (atk / defe) + 2) * stab * effectiveness * expected_hits

        raw_damage = self._apply_weather_mod(raw_damage, move, battle)
        raw_damage = self._apply_terrain_mod(raw_damage, move, battle)

        return raw_damage / defender_hp

    def _score_move(self, move, attacker, defender, battle) -> float:
        """Score a move for the best-move selection phase."""
        if move.base_power <= 1:
            return 0.0

        if move.category == MoveCategory.PHYSICAL:
            atk = self._get_boosted_stat(attacker, "atk")
            defe = self._get_boosted_stat(defender, "def")
            if get_status_name(attacker) == "BRN":
                atk *= 0.5
        elif move.category == MoveCategory.SPECIAL:
            atk = self._get_boosted_stat(attacker, "spa")
            defe = self._get_boosted_stat(defender, "spd")
        else:
            return 0.0

        defe = max(defe, 1.0)

        effectiveness = defender.damage_multiplier(move)
        stab = 1.5 if move.type in attacker.types else 1.0
        accuracy = move.accuracy if isinstance(move.accuracy, float) else 1.0
        expected_hits = move.expected_hits if hasattr(move, "expected_hits") else 1.0

        score = (atk / defe) * move.base_power * stab * effectiveness * accuracy * expected_hits

        score = self._apply_weather_mod(score, move, battle)
        score = self._apply_terrain_mod(score, move, battle)

        if move.entry.get("priority", 0) > 0:
            score *= 1.2

        return float(score)

    # -- Field Modifiers --------------------------------------------------

    @staticmethod
    def _apply_weather_mod(damage: float, move, battle) -> float:
        if not battle.weather:
            return damage
        w_name = str(battle.weather).upper()
        move_type = move.type.name
        if "SUN" in w_name:
            if move_type == "FIRE":
                damage *= 1.5
            elif move_type == "WATER":
                damage *= 0.5
        elif "RAIN" in w_name:
            if move_type == "WATER":
                damage *= 1.5
            elif move_type == "FIRE":
                damage *= 0.5
        return damage

    @staticmethod
    def _apply_terrain_mod(damage: float, move, battle) -> float:
        if not battle.fields:
            return damage
        move_type = move.type.name
        terrain_boosts = {
            "ELECTRIC": "ELECTRIC",
            "GRASSY": "GRASS",
            "PSYCHIC": "PSYCHIC",
        }
        for field in battle.fields:
            f_name = str(field).upper()
            for terrain_key, boosted_type in terrain_boosts.items():
                if terrain_key in f_name and move_type == boosted_type:
                    damage *= 1.3
        return damage
