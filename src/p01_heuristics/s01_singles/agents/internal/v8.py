"""Heuristic V8: Advanced Strategic Battler with Meta Awareness.

Extends V7 with game-knowledge features that go beyond Abyssal:

- **Item Awareness**: Adjusts damage for Life Orb, Choice items, Assault Vest.
- **Ability Immunities**: Recognizes Flash Fire, Levitate, Water/Volt Absorb, etc.
- **Screen Awareness**: Halves expected damage when opponent has Reflect/Light Screen.
- **Trick Room**: Reverses speed comparison when Trick Room is active.
- **Choice Lock Exploitation**: Identifies Choice-locked opponents for free setups.
"""

from __future__ import annotations

from poke_env.environment.field import Field
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

# Abilities that grant type immunities
ABILITY_IMMUNITIES = {
    "flashfire": "FIRE",
    "levitate": "GROUND",
    "voltabsorb": "ELECTRIC",
    "lightningrod": "ELECTRIC",
    "waterabsorb": "WATER",
    "stormdrain": "WATER",
    "dryskin": "WATER",
    "sapsipper": "GRASS",
    "motordrive": "ELECTRIC",
}

# Items that boost offensive stats
CHOICE_ITEMS = {"choiceband", "choicespecs", "choicescarf"}
OFFENSIVE_ITEMS = {
    "lifeorb": 1.3,
    "choiceband": 1.5,
    "choicespecs": 1.5,
}
DEFENSIVE_ITEMS = {
    "assaultvest": ("spd", 1.5),
    "eviolite": ("def_spd", 1.5),
}


class HeuristicV8(BaseHeuristic1v1):
    """Meta-aware heuristic with item/ability/screen/Trick Room knowledge."""

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

        # -- Phase 2: Setup Logic (enhanced with Choice lock detection) --
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
        if not battle.available_moves:
            return None

        btag = battle.battle_tag
        n_opp_remaining = 6 - len([m for m in battle.opponent_team.values() if m.fainted])
        n_remaining = len([m for m in battle.team.values() if not m.fainted])

        if n_opp_remaining >= 3:
            for move in battle.available_moves:
                if move.id in ENTRY_HAZARDS:
                    condition = ENTRY_HAZARDS[move.id]
                    if condition not in battle.opponent_side_conditions:
                        self._hazard_sets_by_battle[btag] = self._hazard_sets_by_battle.get(btag, 0) + 1
                        self._record_used_move(btag, move.id)
                        return self.create_order(move)

        if battle.side_conditions and n_remaining >= 2:
            for move in battle.available_moves:
                if move.id in ANTI_HAZARDS_MOVES:
                    self._hazard_removals_by_battle[btag] = self._hazard_removals_by_battle.get(btag, 0) + 1
                    self._record_used_move(btag, move.id)
                    return self.create_order(move)

        return None

    # -- Setup Logic (enhanced) -------------------------------------------

    def _setup_logic(self, battle, me, opp):
        """Use boost moves when safe. Also triggers on Choice-locked opponents."""
        can_setup = False

        if me.current_hp_fraction >= 1.0 and self._estimate_matchup(me, opp, battle) > 0:
            can_setup = True

        if not can_setup and self._opponent_choice_locked(opp, me):
            can_setup = True

        if not can_setup:
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

    @staticmethod
    def _opponent_choice_locked(opp, me) -> bool:
        """Detect if the opponent is likely Choice-locked into a resisted move."""
        opp_item = opp.item if hasattr(opp, "item") else None
        if not opp_item:
            return False

        item_str = str(opp_item).lower().replace(" ", "").replace("-", "")
        if item_str not in CHOICE_ITEMS:
            return False

        # If opponent has a known last move and we resist it, we're safe to setup
        if hasattr(opp, "moves") and opp.moves:
            for move in opp.moves.values():
                if hasattr(move, "current_pp") and move.current_pp is not None:
                    if me.damage_multiplier(move) <= 0.5:
                        return True

        return False

    # -- Switching --------------------------------------------------------

    def _should_switch_out(self, battle, me, opp) -> bool:
        if not [s for s in battle.available_switches if self._estimate_matchup(s, opp, battle) > 0]:
            return False

        if me.boosts.get("def", 0) <= -3 or me.boosts.get("spd", 0) <= -3:
            return True

        me_stats = me.stats or me.base_stats or {}
        if me.boosts.get("atk", 0) <= -3 and me_stats.get("atk", 0) >= me_stats.get("spa", 0):
            return True
        if me.boosts.get("spa", 0) <= -3 and me_stats.get("atk", 0) <= me_stats.get("spa", 0):
            return True

        if self._estimate_matchup(me, opp, battle) < SWITCH_OUT_MATCHUP_THRESHOLD:
            return True

        return False

    def _get_best_switch(self, battle):
        opp = battle.opponent_active_pokemon
        if opp is None:
            return None

        return max(
            battle.available_switches,
            key=lambda s: self._estimate_matchup(s, opp, battle),
        )

    # -- Matchup Estimation (Trick Room aware) ----------------------------

    def _estimate_matchup(self, mon, opponent, battle=None) -> float:
        mon_types = [t for t in mon.types if t is not None]
        opp_types = [t for t in opponent.types if t is not None]

        if not mon_types or not opp_types:
            return 0.0

        score = max(opponent.damage_multiplier(t) for t in mon_types)
        score -= max(mon.damage_multiplier(t) for t in opp_types)

        mon_speed = mon.base_stats.get("spe", 100) if mon.base_stats else 100
        opp_speed = opponent.base_stats.get("spe", 100) if opponent.base_stats else 100

        # Trick Room reversal
        trick_room_active = False
        if battle and battle.fields:
            for field in battle.fields:
                if "TRICK" in str(field).upper():
                    trick_room_active = True
                    break

        if trick_room_active:
            mon_speed, opp_speed = opp_speed, mon_speed

        if mon_speed > opp_speed:
            score += SPEED_TIER_COEFF
        elif opp_speed > mon_speed:
            score -= SPEED_TIER_COEFF

        score += mon.current_hp_fraction * HP_FRACTION_COEFF
        score -= opponent.current_hp_fraction * HP_FRACTION_COEFF

        return score

    # -- Damage Estimation (with item/ability/screen awareness) -----------

    def _get_boosted_stat(self, pokemon, stat_name: str) -> float:
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

    def _get_item_offense_mult(self, attacker, move) -> float:
        """Get offensive multiplier from the attacker's item."""
        item = attacker.item if hasattr(attacker, "item") and attacker.item else None
        if not item:
            return 1.0

        item_str = str(item).lower().replace(" ", "").replace("-", "")

        if item_str == "lifeorb":
            return 1.3
        if item_str == "choiceband" and move.category == MoveCategory.PHYSICAL:
            return 1.5
        if item_str == "choicespecs" and move.category == MoveCategory.SPECIAL:
            return 1.5

        return 1.0

    def _get_item_defense_mult(self, defender, move) -> float:
        """Get defensive multiplier from the defender's item."""
        item = defender.item if hasattr(defender, "item") and defender.item else None
        if not item:
            return 1.0

        item_str = str(item).lower().replace(" ", "").replace("-", "")

        if item_str == "assaultvest" and move.category == MoveCategory.SPECIAL:
            return 1.5
        if item_str == "eviolite":
            return 1.5

        return 1.0

    def _check_ability_immunity(self, move, defender) -> bool:
        """Return True if the defender's ability makes it immune to this move type."""
        ability = defender.ability if hasattr(defender, "ability") and defender.ability else None
        if not ability:
            return False

        ability_str = str(ability).lower().replace(" ", "").replace("-", "")
        immune_type = ABILITY_IMMUNITIES.get(ability_str)
        if immune_type and move.type.name == immune_type:
            return True

        return False

    def _get_screen_mult(self, move, battle) -> float:
        """Check if opponent has screens that reduce our damage."""
        if not battle.opponent_side_conditions:
            return 1.0

        has_aurora = any("AURORA" in str(sc).upper() for sc in battle.opponent_side_conditions)
        if has_aurora:
            return 0.5

        if move.category == MoveCategory.PHYSICAL:
            has_reflect = any("REFLECT" in str(sc).upper() for sc in battle.opponent_side_conditions)
            if has_reflect:
                return 0.5
        elif move.category == MoveCategory.SPECIAL:
            has_light_screen = any("LIGHT" in str(sc).upper() for sc in battle.opponent_side_conditions)
            if has_light_screen:
                return 0.5

        return 1.0

    def _estimate_damage_fraction(self, move, attacker, defender, battle) -> float:
        """Estimate damage as a fraction of defender's max HP."""
        if move.base_power <= 1:
            return 0.0

        if self._check_ability_immunity(move, defender):
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

        # Apply item modifiers
        atk *= self._get_item_offense_mult(attacker, move)
        defe *= self._get_item_defense_mult(defender, move)

        effectiveness = defender.damage_multiplier(move)
        stab = 1.5 if move.type in attacker.types else 1.0
        expected_hits = move.expected_hits if hasattr(move, "expected_hits") else 1.0

        defender_hp = defender.max_hp if hasattr(defender, "max_hp") and defender.max_hp else 300
        raw_damage = (0.44 * move.base_power * (atk / defe) + 2) * stab * effectiveness * expected_hits

        raw_damage = self._apply_weather_mod(raw_damage, move, battle)
        raw_damage = self._apply_terrain_mod(raw_damage, move, battle)
        raw_damage *= self._get_screen_mult(move, battle)

        return raw_damage / defender_hp

    def _score_move(self, move, attacker, defender, battle) -> float:
        """Score a move for the best-move selection phase."""
        if move.base_power <= 1:
            return 0.0

        if self._check_ability_immunity(move, defender):
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

        # Apply item modifiers
        atk *= self._get_item_offense_mult(attacker, move)
        defe *= self._get_item_defense_mult(defender, move)

        effectiveness = defender.damage_multiplier(move)
        stab = 1.5 if move.type in attacker.types else 1.0
        accuracy = move.accuracy if isinstance(move.accuracy, float) else 1.0
        expected_hits = move.expected_hits if hasattr(move, "expected_hits") else 1.0

        score = (atk / defe) * move.base_power * stab * effectiveness * accuracy * expected_hits

        score = self._apply_weather_mod(score, move, battle)
        score = self._apply_terrain_mod(score, move, battle)
        score *= self._get_screen_mult(move, battle)

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
