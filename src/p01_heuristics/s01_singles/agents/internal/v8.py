"""Heuristic V8: Attack-First Meta Reader.

V7's attack-first discipline plus meta-game awareness:

- **Item Awareness**: Life Orb, Choice Band/Specs boost our damage estimate;
  Assault Vest, Eviolite reduce expected damage on opponent.
- **Ability Immunities**: Skip moves the opponent is immune to (Flash Fire, etc.).
- **Screen Awareness**: Halves expected damage through Reflect/Light Screen/Aurora Veil.
- **Trick Room**: Reverses speed comparison when active.
- **Choice Lock Exploitation**: Free setup when opponent locked into resisted move.
- **Same Attack-First Core**: Attacks ~80% of turns, strategic only when clearly free.
"""

from __future__ import annotations

from poke_env.environment.move_category import MoveCategory
from poke_env.environment.side_condition import SideCondition

from ...core.base import BaseHeuristic1v1
from ...core.common import get_speed, get_status_name


ENTRY_HAZARDS = {
    "spikes": SideCondition.SPIKES,
    "stealthrock": SideCondition.STEALTH_ROCK,
    "stickyweb": SideCondition.STICKY_WEB,
    "toxicspikes": SideCondition.TOXIC_SPIKES,
}
ANTI_HAZARDS_MOVES = {"rapidspin", "defog"}

SPEED_TIER_COEFF = 0.1
HP_FRACTION_COEFF = 0.4
SWITCH_OUT_MATCHUP_THRESHOLD = -4
WEAK_MOVE_THRESHOLD = 20

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

CHOICE_ITEMS = {"choiceband", "choicespecs", "choicescarf"}


class HeuristicV8(BaseHeuristic1v1):
    """Attack-first meta reader: V7 discipline + item/ability/screen awareness."""

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
            if self._check_ability_immunity(move, opp):
                continue
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

        my_status = get_status_name(me)
        opp_status = get_status_name(opp)
        my_speed = get_speed(me, my_status)
        opp_speed = get_speed(opp, opp_status)

        # -- Phase 1: Score all moves (meta-aware damage) --
        best_move = None
        max_score = -1.0
        max_raw_damage = -1.0

        for move in battle.available_moves or []:
            if self._check_ability_immunity(move, opp):
                continue

            dmg = self._meta_aware_damage(move, me, opp, my_status, battle)
            if dmg > max_raw_damage:
                max_raw_damage = dmg

            score = self._score_move(move, dmg, battle)
            if score > max_score:
                max_score, best_move = score, move

        # -- Phase 2: V2/V3 proven defensive pivots --
        if battle.available_switches:
            if my_status == "TOX" and me.status_counter > 2:
                switch = self._get_best_switch(battle)
                if switch:
                    return self.create_order(switch)
                return self.create_order(battle.available_switches[0])

            if max_raw_damage < WEAK_MOVE_THRESHOLD and my_speed < opp_speed:
                switch = self._get_best_switch(battle)
                if switch:
                    return self.create_order(switch)
                return self.create_order(battle.available_switches[0])

        # -- Phase 3: Hazards ONLY when turn is free --
        if self._is_free_turn(me, opp, my_speed, opp_speed):
            hazard_order = self._hazard_logic(battle)
            if hazard_order:
                return hazard_order

        # -- Phase 4: Setup when opponent can't 2HKO OR choice-locked --
        if self._safe_to_setup(me, opp, battle) or self._opponent_choice_locked(opp, me):
            setup_order = self._setup_logic(battle, me)
            if setup_order:
                return setup_order

        # -- Phase 5: Catastrophic matchup switch (threshold -4) --
        if battle.available_switches and self._should_matchup_switch(me, opp, battle):
            switch = self._get_best_switch(battle)
            if switch:
                btag = battle.battle_tag
                self._matchup_switches_by_battle[btag] = self._matchup_switches_by_battle.get(btag, 0) + 1
                return self.create_order(switch)

        # -- Phase 6: Default — attack with best move --
        if best_move:
            self._record_used_move(battle.battle_tag, best_move.id)
            return self.create_order(best_move)

        return None

    # -- Meta-Aware Damage ------------------------------------------------

    def _meta_aware_damage(self, move, attacker, defender, attacker_status, battle) -> float:
        """Stat-based damage with item/screen awareness."""
        if move.base_power <= 1:
            return 0.0

        if move.category == MoveCategory.PHYSICAL:
            atk = self._get_boosted_stat(attacker, "atk")
            defe = self._get_boosted_stat(defender, "def")
            if attacker_status == "BRN":
                atk *= 0.5
        elif move.category == MoveCategory.SPECIAL:
            atk = self._get_boosted_stat(attacker, "spa")
            defe = self._get_boosted_stat(defender, "spd")
        else:
            return 0.0

        defe = max(defe, 1.0)

        atk *= self._get_item_offense_mult(attacker, move)
        defe *= self._get_item_defense_mult(defender, move)

        effectiveness = defender.damage_multiplier(move)
        stab = 1.5 if move.type in attacker.types else 1.0

        damage = (atk / defe) * move.base_power * stab * effectiveness
        damage *= self._get_screen_mult(move, battle)

        return float(damage)

    # -- Move Scoring -----------------------------------------------------

    def _score_move(self, move, raw_damage: float, battle) -> float:
        """Score: raw_damage × weather × terrain × accuracy × priority."""
        if raw_damage <= 0:
            return 0.0

        score = raw_damage
        score = self._apply_weather_mod(score, move, battle)
        score = self._apply_terrain_mod(score, move, battle)

        accuracy = move.accuracy if isinstance(move.accuracy, float) else 1.0
        score *= accuracy

        if move.entry.get("priority", 0) > 0:
            score *= 1.2

        return float(score)

    # -- Free Turn Detection (for hazards) --------------------------------

    def _is_free_turn(self, me, opp, my_speed, opp_speed) -> bool:
        """Free if we outspeed AND resist opponent's STAB types."""
        if my_speed <= opp_speed:
            return False

        opp_types = [t for t in opp.types if t is not None]
        if not opp_types:
            return False

        max_threat = max(me.damage_multiplier(t) for t in opp_types)
        return max_threat <= 1.0

    # -- Hazard Logic (only on free turns) --------------------------------

    def _hazard_logic(self, battle):
        """Set hazards or clear own hazards when it's safe."""
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

    # -- Setup Logic (2HKO safety check + choice lock) --------------------

    def _safe_to_setup(self, me, opp, battle) -> bool:
        """Only setup if opponent cannot 2HKO us."""
        if me.current_hp_fraction < 0.8:
            return False

        opp_max_damage_fraction = self._estimate_opponent_best_damage(me, opp, battle)
        return opp_max_damage_fraction * 2 < me.current_hp_fraction

    def _estimate_opponent_best_damage(self, defender, attacker, battle) -> float:
        """Estimate opponent's best STAB damage against us as HP fraction."""
        opp_types = [t for t in attacker.types if t is not None]
        if not opp_types:
            return 0.3

        opp_atk = self._get_boosted_stat(attacker, "atk")
        opp_spa = self._get_boosted_stat(attacker, "spa")
        our_def = self._get_boosted_stat(defender, "def")
        our_spd = self._get_boosted_stat(defender, "spd")

        our_def = max(our_def, 1.0)
        our_spd = max(our_spd, 1.0)

        # Account for opponent's offensive item
        opp_item_mult = 1.0
        opp_item = attacker.item if hasattr(attacker, "item") and attacker.item else None
        if opp_item:
            item_str = str(opp_item).lower().replace(" ", "").replace("-", "")
            if item_str in ("lifeorb", "choiceband", "choicespecs"):
                opp_item_mult = 1.3 if item_str == "lifeorb" else 1.5

        # Account for our defensive item
        our_def_item_phys = 1.0
        our_def_item_spec = 1.0
        our_item = defender.item if hasattr(defender, "item") and defender.item else None
        if our_item:
            item_str = str(our_item).lower().replace(" ", "").replace("-", "")
            if item_str == "eviolite":
                our_def_item_phys = 1.5
                our_def_item_spec = 1.5
            elif item_str == "assaultvest":
                our_def_item_spec = 1.5

        best_fraction = 0.0
        for opp_type in opp_types:
            effectiveness = defender.damage_multiplier(opp_type)
            phys_damage = (0.44 * 80 * (opp_atk * opp_item_mult / (our_def * our_def_item_phys)) + 2) * 1.5 * effectiveness
            spec_damage = (0.44 * 80 * (opp_spa * opp_item_mult / (our_spd * our_def_item_spec)) + 2) * 1.5 * effectiveness
            best_type_damage = max(phys_damage, spec_damage)

            defender_hp = defender.max_hp if hasattr(defender, "max_hp") and defender.max_hp else 300
            fraction = best_type_damage / defender_hp
            if fraction > best_fraction:
                best_fraction = fraction

        return best_fraction

    @staticmethod
    def _opponent_choice_locked(opp, me) -> bool:
        """Detect if opponent is Choice-locked into a move we resist."""
        opp_item = opp.item if hasattr(opp, "item") else None
        if not opp_item:
            return False

        item_str = str(opp_item).lower().replace(" ", "").replace("-", "")
        if item_str not in CHOICE_ITEMS:
            return False

        if hasattr(opp, "moves") and opp.moves:
            for move in opp.moves.values():
                if hasattr(move, "current_pp") and move.current_pp is not None:
                    if me.damage_multiplier(move) <= 0.5:
                        return True

        return False

    def _setup_logic(self, battle, me):
        """Use a boost move if setup conditions are met."""
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

    # -- Catastrophic Switching -------------------------------------------

    def _should_matchup_switch(self, me, opp, battle) -> bool:
        """Only switch on truly catastrophic matchups (threshold -4)."""
        return self._estimate_matchup(me, opp, battle) < SWITCH_OUT_MATCHUP_THRESHOLD

    def _get_best_switch(self, battle):
        """Pick teammate with best defensive typing vs opponent."""
        opp = battle.opponent_active_pokemon
        if opp is None:
            return None

        best_teammate = None
        min_multiplier = 4.0

        for pokemon in battle.available_switches:
            valid_types = [t for t in opp.types if t is not None]
            if not valid_types:
                worst = 1.0
            else:
                worst = max(pokemon.damage_multiplier(t) for t in valid_types)

            if worst < min_multiplier:
                min_multiplier = worst
                best_teammate = pokemon

        return best_teammate if min_multiplier <= 2.0 else None

    # -- Matchup Estimation (Trick Room aware) ----------------------------

    def _estimate_matchup(self, mon, opponent, battle=None) -> float:
        """Type matchup + speed tier + HP, with Trick Room reversal."""
        mon_types = [t for t in mon.types if t is not None]
        opp_types = [t for t in opponent.types if t is not None]

        if not mon_types or not opp_types:
            return 0.0

        score = max(opponent.damage_multiplier(t) for t in mon_types)
        score -= max(mon.damage_multiplier(t) for t in opp_types)

        mon_speed = mon.base_stats.get("spe", 100) if mon.base_stats else 100
        opp_speed = opponent.base_stats.get("spe", 100) if opponent.base_stats else 100

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

    # -- Damage Estimation (for KO check) ---------------------------------

    def _estimate_damage_fraction(self, move, attacker, defender, battle) -> float:
        """Estimate damage as a fraction of defender's max HP (meta-aware)."""
        if move.base_power <= 1:
            return 0.0

        if self._check_ability_immunity(move, defender):
            return 0.0

        attacker_status = get_status_name(attacker)

        if move.category == MoveCategory.PHYSICAL:
            atk = self._get_boosted_stat(attacker, "atk")
            defe = self._get_boosted_stat(defender, "def")
            if attacker_status == "BRN":
                atk *= 0.5
        elif move.category == MoveCategory.SPECIAL:
            atk = self._get_boosted_stat(attacker, "spa")
            defe = self._get_boosted_stat(defender, "spd")
        else:
            return 0.0

        defe = max(defe, 1.0)

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

    # -- Meta Awareness Helpers -------------------------------------------

    @staticmethod
    def _check_ability_immunity(move, defender) -> bool:
        """Return True if defender's ability makes it immune to this move type."""
        ability = defender.ability if hasattr(defender, "ability") and defender.ability else None
        if not ability:
            return False

        ability_str = str(ability).lower().replace(" ", "").replace("-", "")
        immune_type = ABILITY_IMMUNITIES.get(ability_str)
        if immune_type and move.type.name == immune_type:
            return True

        return False

    @staticmethod
    def _get_item_offense_mult(attacker, move) -> float:
        """Offensive multiplier from attacker's item."""
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

    @staticmethod
    def _get_item_defense_mult(defender, move) -> float:
        """Defensive multiplier from defender's item."""
        item = defender.item if hasattr(defender, "item") and defender.item else None
        if not item:
            return 1.0

        item_str = str(item).lower().replace(" ", "").replace("-", "")

        if item_str == "assaultvest" and move.category == MoveCategory.SPECIAL:
            return 1.5
        if item_str == "eviolite":
            return 1.5

        return 1.0

    @staticmethod
    def _get_screen_mult(move, battle) -> float:
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
