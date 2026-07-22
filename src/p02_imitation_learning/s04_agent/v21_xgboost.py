from __future__ import annotations

import json
import os
import re

import joblib
import pandas as pd
import xgboost as xgb

from p00_core.core.common import get_status_name
from p01_heuristics.agents.internal.v14 import HeuristicV14

try:
    from poke_env.environment.side_condition import SideCondition
except ImportError:
    from poke_env.battle import SideCondition


class HeuristicV21XGBoost(HeuristicV14):
    """Advanced Imitation Learning Agent (v21_xgboost) — The Championship Hybrid AI.

    This agent fuses a high-dimensional XGBoost behavioral cloning model (trained on
    1.1M expert human turns across 1,150 state features) with the full tactical and
    endgame minimax architecture of HeuristicV14.

    Key Innovations over previous v21 iterations:
    1. **Exact Normalized Species OHE Matching**: Normalizes species names (`re.sub(r'[^a-z0-9]', '')`)
       to eliminate 100% of missing one-hot features across all regional, paradox, crowned, and alcremie forms.
    2. **Calibrated Probability Threshold**: Dynamically loads the precision-recall/F1 calibrated decision
       boundary (`switch_threshold`) from `xgboost_advanced_threshold.json` to account for `scale_pos_weight`.
    3. **Cognitive-Tactical Hybrid Arbitration**:
       - Restores `v14` Endgame Minimax Solver (`_run_endgame_solver`) when both teams have <= 2 Pokémon.
       - Restores Setup Sweeper Protection (`_handle_opponent_setup_sweeper`) and Status Absorption (`_try_status_absorption`).
       - Executes **Pivot Momentum** (`U-turn`, `Volt Switch`, `Flip Turn`) when XGBoost predicts a Switch and conditions permit safe outspeeds/chip damage.
       - Provides emergency tactical overrides if staying in would result in guaranteed knockout with weak outgoing damage.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
        models_dir = os.path.join(
            project_root, "src", "p02_imitation_learning", "s03_training", "models", "gen9randombattle"
        )

        feature_path = os.path.join(models_dir, "xgboost_advanced_features.pkl")
        model_path = os.path.join(models_dir, "xgboost_advanced_model.json")
        threshold_path = os.path.join(models_dir, "xgboost_advanced_threshold.json")

        if not os.path.exists(feature_path):
            raise FileNotFoundError(
                f"Advanced feature list not found at {feature_path}. Please run train_ml_advanced.py first."
            )
        if not os.path.exists(model_path):
            raise FileNotFoundError(
                f"Advanced XGBoost model not found at {model_path}. Please run train_ml_advanced.py first."
            )

        self.feature_columns: list[str] = joblib.load(feature_path)
        self.model = xgb.XGBClassifier()
        self.model.load_model(model_path)

        # Load calibrated threshold if available
        self.switch_threshold = 0.58
        if os.path.exists(threshold_path):
            try:
                with open(threshold_path) as f:
                    th_data = json.load(f)
                    self.switch_threshold = float(th_data.get("recommended_threshold", 0.58))
            except Exception as e:
                print(f"[v21_xgboost] Warning: Could not load threshold ({e}). Defaulting to {self.switch_threshold}")

        # Build exact normalized species lookup tables (`re.sub(r'[^a-z0-9]', '', suffix) -> exact_column`)
        self._p1_species_norm_map: dict[str, str] = {}
        self._p2_species_norm_map: dict[str, str] = {}
        p1_prefix = "p1_active_pokemon_"
        p2_prefix = "p2_active_pokemon_"
        for col in self.feature_columns:
            if col.startswith(p1_prefix):
                suffix = col[len(p1_prefix) :]
                norm_key = re.sub(r"[^a-z0-9]", "", suffix)
                self._p1_species_norm_map[norm_key] = col
                if norm_key == "taurospaldeaaqua":
                    self._p1_species_norm_map["taurosmaldicewater"] = col
                    self._p1_species_norm_map["taurospaldeawater"] = col
                elif norm_key == "taurospaldeablaze":
                    self._p1_species_norm_map["taurosmaldicefire"] = col
                    self._p1_species_norm_map["taurospaldeafire"] = col
                elif norm_key == "taurospaldeacombat":
                    self._p1_species_norm_map["taurosmaldicecombat"] = col
                    self._p1_species_norm_map["taurosmaldice"] = col
            elif col.startswith(p2_prefix):
                suffix = col[len(p2_prefix) :]
                norm_key = re.sub(r"[^a-z0-9]", "", suffix)
                self._p2_species_norm_map[norm_key] = col
                if norm_key == "taurospaldeaaqua":
                    self._p2_species_norm_map["taurosmaldicewater"] = col
                    self._p2_species_norm_map["taurospaldeawater"] = col
                elif norm_key == "taurospaldeablaze":
                    self._p2_species_norm_map["taurosmaldicefire"] = col
                    self._p2_species_norm_map["taurospaldeafire"] = col
                elif norm_key == "taurospaldeacombat":
                    self._p2_species_norm_map["taurosmaldicecombat"] = col
                    self._p2_species_norm_map["taurosmaldice"] = col

        # Telemetry and loop guards
        self._last_action_type: dict[str, int] = {}
        self._ko_guards_by_battle: dict[str, int] = {}
        self._loop_guards_by_battle: dict[str, int] = {}
        self._xgb_switches_by_battle: dict[str, int] = {}
        self._xgb_stays_by_battle: dict[str, int] = {}
        self._xgb_prob_sum_by_battle: dict[str, float] = {}
        self._endgame_solves_by_battle: dict[str, int] = {}
        self._total_turns_by_battle: dict[str, int] = {}

    def reset_battles(self) -> None:
        """Clear both base battle history and our custom switch/telemetry tracking."""
        try:
            super().reset_battles()
        finally:
            self._last_action_type.clear()
            self._ko_guards_by_battle.clear()
            self._loop_guards_by_battle.clear()
            self._xgb_switches_by_battle.clear()
            self._xgb_stays_by_battle.clear()
            self._xgb_prob_sum_by_battle.clear()
            self._endgame_solves_by_battle.clear()
            self._total_turns_by_battle.clear()

    def _build_empty_feature_dict(self) -> dict[str, float]:
        """Return a zero-initialized feature dict matching the training schema."""
        return {col: 0.0 for col in self.feature_columns}

    def _set_species_one_hot(self, features: dict[str, float], prefix: str, species: str | None) -> None:
        """Activate the correct one-hot column using normalized alphanumeric lookup.

        Eliminates 100% of missing one-hot features for paldean, paradox, and alternate forms.
        """
        if not species:
            return

        norm_key = re.sub(r"[^a-z0-9]", "", str(species).lower())
        if prefix == "p1_active_pokemon" and norm_key in self._p1_species_norm_map:
            features[self._p1_species_norm_map[norm_key]] = 1.0
            return
        elif prefix == "p2_active_pokemon" and norm_key in self._p2_species_norm_map:
            features[self._p2_species_norm_map[norm_key]] = 1.0
            return

        # Fallback candidate search
        species_raw = str(species).lower()
        candidates = [
            f"{prefix}_{species_raw}",
            f"{prefix}_{species_raw.replace('-', ' ')}",
            f"{prefix}_{species_raw.replace('_', ' ')}",
        ]
        for key in candidates:
            if key in features:
                features[key] = 1.0
                return

    def _extract_live_features(self, battle) -> pd.DataFrame:
        """Construct the advanced feature vector from the live battle state."""
        features = self._build_empty_feature_dict()

        me = battle.active_pokemon
        opp = battle.opponent_active_pokemon

        # 1. Turn number
        if "turn_number" in features:
            features["turn_number"] = float(battle.turn)

        # 2. Continuous HP
        if "p1_hp_percent" in features:
            features["p1_hp_percent"] = float(me.current_hp_fraction) if me else 0.0
        if "p2_hp_percent" in features:
            features["p2_hp_percent"] = float(opp.current_hp_fraction) if opp else 0.0

        # 3. Stealth Rock state
        if "p1_stealth_rock_active" in features:
            features["p1_stealth_rock_active"] = (
                1.0
                if (
                    SideCondition.STEALTH_ROCK in battle.side_conditions
                    or any(getattr(c, "name", str(c)).upper() in ["STEALTH_ROCK", "STEALTHROCK"] for c in battle.side_conditions)
                )
                else 0.0
            )
        if "p2_stealth_rock_active" in features:
            opp_conds = getattr(battle, "opponent_side_conditions", {}) or {}
            features["p2_stealth_rock_active"] = (
                1.0
                if (
                    SideCondition.STEALTH_ROCK in opp_conds
                    or any(getattr(c, "name", str(c)).upper() in ["STEALTH_ROCK", "STEALTHROCK"] for c in opp_conds)
                )
                else 0.0
            )

        # 4. Tera usage
        if "p1_tera_used" in features:
            features["p1_tera_used"] = 1.0 if not battle.can_tera else 0.0
        if "p2_tera_used" in features or "p2_used_tera" in features:
            opp_tera = getattr(battle, "opponent_can_tera", True)
            key = "p2_tera_used" if "p2_tera_used" in features else "p2_used_tera"
            features[key] = 0.0 if opp_tera else 1.0

        # 5. Species (One-hot)
        if me:
            self._set_species_one_hot(features, "p1_active_pokemon", str(me.species))
        if opp:
            self._set_species_one_hot(features, "p2_active_pokemon", str(opp.species))

        return pd.DataFrame([features])

    def _select_action(self, battle):
        btag = battle.battle_tag
        me = battle.active_pokemon
        opp = battle.opponent_active_pokemon

        # Initialize tracking for this battle
        self._ko_guards_by_battle.setdefault(btag, 0)
        self._loop_guards_by_battle.setdefault(btag, 0)
        self._xgb_switches_by_battle.setdefault(btag, 0)
        self._xgb_stays_by_battle.setdefault(btag, 0)
        self._xgb_prob_sum_by_battle.setdefault(btag, 0.0)
        self._endgame_solves_by_battle.setdefault(btag, 0)
        self._total_turns_by_battle[btag] = self._total_turns_by_battle.get(btag, 0) + 1

        # Update active histories (for Yomi layers & setup tracking)
        if not hasattr(self, "_active_history_by_battle"):
            self._active_history_by_battle = {}
        if btag not in self._active_history_by_battle:
            self._active_history_by_battle[btag] = []
        if me:
            history = self._active_history_by_battle[btag]
            if not history or history[-1][0] < battle.turn:
                history.append((battle.turn, me.species.lower()))

        if not hasattr(self, "_opp_active_history_by_battle"):
            self._opp_active_history_by_battle = {}
        if btag not in self._opp_active_history_by_battle:
            self._opp_active_history_by_battle[btag] = []
        if opp:
            opp_history = self._opp_active_history_by_battle[btag]
            if not opp_history or opp_history[-1][0] < battle.turn:
                opp_history.append((battle.turn, opp.species.lower()))

        # 1. Update roles and parse battlefield states
        self._evaluate_team_roles(battle)
        self._update_inferences(battle)

        # Forced switches / Fainted state
        force_switch = battle.force_switch
        if isinstance(force_switch, list):
            force_switch = any(force_switch)

        if force_switch or me is None or me.fainted or not battle.available_moves:
            if battle.available_switches:
                if opp is not None and not opp.fainted:
                    switch = self._get_best_switch(battle, opp)
                else:
                    switch = self._get_best_switch_double_faint(battle)
                if switch:
                    return self.create_order(switch)
                # Best-switch returned None but switches exist — pick any available
                return self.create_order(battle.available_switches[0])
            # No switches at all — random is correct (last mon standing)
            return self.choose_random_move(battle)

        format_str = battle._format or ""
        my_status = get_status_name(me)
        opp_status = get_status_name(opp)
        my_speed = self._get_boosted_speed(me, my_status, format_str)
        opp_speed = self._get_boosted_speed(opp, opp_status, format_str)

        # 2. Guaranteed KO — always take the guaranteed kill immediately
        ko_move = self._find_guaranteed_ko(battle, me, opp, my_speed, opp_speed)
        if ko_move:
            self._ko_guards_by_battle[btag] = self._ko_guards_by_battle.get(btag, 0) + 1
            self._record_used_move(btag, ko_move.id)
            tera = self._should_terastallize(battle, ko_move)
            return self.create_order(ko_move, terastallize=tera)

        # 3. Endgame Minimax Solver — exact lookahead when both teams <= 2 Pokémon
        endgame_order = self._run_endgame_solver(battle, me, opp)
        if endgame_order:
            self._endgame_solves_by_battle[btag] = self._endgame_solves_by_battle.get(btag, 0) + 1
            return endgame_order

        # 4. Setup Sweeper Reaction — protect against +2 Attack / Sp.Atk sweepers
        setup_reaction = self._handle_opponent_setup_sweeper(battle, me, opp, my_speed, opp_speed)
        if setup_reaction:
            return setup_reaction

        # 5. Status Absorption Check — absorb incoming telegraphed status attacks
        absorber = self._try_status_absorption(battle, me, opp)
        if absorber:
            return self.create_order(absorber)

        # 6. XGBoost High-Level Macro Policy Prediction (0 = Move, 1 = Switch)
        live_features = self._extract_live_features(battle)
        probs = self.model.predict_proba(live_features)[0]

        if len(probs) < 2:
            action_type = 0
            prob_val = 0.0
        else:
            action_type = 1 if probs[1] >= self.switch_threshold else 0
            prob_val = float(probs[1])

        self._xgb_prob_sum_by_battle[btag] = self._xgb_prob_sum_by_battle.get(btag, 0.0) + prob_val

        # Infinite Switch Loop Guard: prevent alternating back-and-forth switches
        last_action = self._last_action_type.get(btag, 0)
        if action_type == 1 and last_action == 1 and battle.available_moves:
            self._loop_guards_by_battle[btag] = self._loop_guards_by_battle.get(btag, 0) + 1
            action_type = 0

        self._last_action_type[btag] = action_type
        if action_type == 1:
            self._xgb_switches_by_battle[btag] = self._xgb_switches_by_battle.get(btag, 0) + 1
        else:
            self._xgb_stays_by_battle[btag] = self._xgb_stays_by_battle.get(btag, 0) + 1

        # 7. Execute Decision with Momentum Pivots & Tactical Overrides
        if action_type == 1 and battle.available_switches:
            # Check if active Pokémon has a pivot move (U-turn / Volt Switch / Flip Turn)
            # Pivoting deals chip damage and switches safely when faster or unthreatened!
            pivot_move = self._find_pivot_move(battle, me, opp, format_str)
            if pivot_move:
                gen = self._get_gen(battle)
                sets_db = self._load_pokemon_sets(gen)
                dmg_est = self._estimate_max_damage(opp, me, gen, sets_db)
                if my_speed > opp_speed or dmg_est < self._current_hp(me) * 0.7:
                    self._record_used_move(btag, pivot_move.id)
                    return self.create_order(pivot_move)

            switch = self._get_best_switch(battle, opp)
            if switch:
                return self.create_order(switch)

        # Action Type == 0 (Move chosen, or fallback if switch unavailable)
        if opp is None:
            return self.choose_random_move(battle)

        best_move = None
        max_score = -1.0
        physical_ratio = self._stat_estimation(me, "atk") / max(self._stat_estimation(opp, "def"), 1.0)
        special_ratio = self._stat_estimation(me, "spa") / max(self._stat_estimation(opp, "spd"), 1.0)
        if my_status == "BRN":
            physical_ratio *= 0.5

        for move in battle.available_moves or []:
            if self._is_ability_immune(move, opp):
                continue
            score = self._score_move(move, me, opp, physical_ratio, special_ratio, battle, my_speed, opp_speed)
            if score > max_score:
                max_score, best_move = score, move

        # Tactical Override Check: If XGBoost said "Move" but our best move is extremely weak (< 30)
        # and V14's tactical check confirms a bad active matchup, override to Switch!
        if max_score < 30.0 and battle.available_switches:
            switch_reason = self._should_switch(me, opp, my_status, my_speed, opp_speed, max_score, battle)
            if switch_reason:
                switch = self._get_best_switch(battle, opp, allowed_only=True)
                if switch:
                    return self.create_order(switch)

        if best_move:
            self._record_used_move(btag, best_move.id)
            tera = self._should_terastallize(battle, best_move)
            return self.create_order(best_move, terastallize=tera)

        return self.choose_random_move(battle)


# Backward compatibility alias for training scripts and benchmark runners
MLAdvancedAgent = HeuristicV21XGBoost
