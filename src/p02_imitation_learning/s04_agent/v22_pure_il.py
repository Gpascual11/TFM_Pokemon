"""HeuristicV22PureIL (v22_pure_il) — Pure End-to-End Imitation Learning Agent.

Unlike `v21_xgboost` which relies on `HeuristicV14` (`v14`) for damage math and tactical
execution, `v22_pure_il` inherits ONLY from `BaseHeuristic1v1` (`p00_core/core/base.py`).
It performs all decisions using two trained XGBoost models:

1. **Macro Policy Engine (`xgboost_advanced_model.json`)**:
   - Evaluates the 1,150-dimensional live battle state to predict Move (`0`) vs Switch (`1`).
   - For switching (`action_type == 1`), performs **Counterfactual Policy Evaluation**:
     scores every bench candidate `c` by passing `c.species` into the macro model and
     selecting the candidate with the highest expert stay probability (`argmin prob_switch`).
2. **Move Policy Engine (`xgboost_move_evaluator.json`)**:
   - For attacking (`action_type == 0`), scores each available move based on its conditional
     candidate features (`base_power`, `STAB`, `type_multiplier`, `is_status`), selecting
     the move predicted to have the highest expert preference.
"""

from __future__ import annotations

import json
import os
import random
import re

import joblib
import pandas as pd
import xgboost as xgb

from p00_core.core.base import BaseHeuristic1v1

try:
    from poke_env.environment.side_condition import SideCondition
except ImportError:
    from poke_env.battle import SideCondition


class HeuristicV22PureIL(BaseHeuristic1v1):
    """Pure Imitation Learning Agent (`v22_pure_il`) — ZERO dependency on HeuristicV14."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
        models_dir = os.path.join(
            project_root, "src", "p02_imitation_learning", "s03_training", "models", "gen9randombattle"
        )

        macro_feat_path = os.path.join(models_dir, "xgboost_advanced_features.pkl")
        macro_model_path = os.path.join(models_dir, "xgboost_advanced_model.json")
        threshold_path = os.path.join(models_dir, "xgboost_advanced_threshold.json")

        move_feat_path = os.path.join(models_dir, "xgboost_move_features.pkl")
        move_model_path = os.path.join(models_dir, "xgboost_move_evaluator.json")

        if not os.path.exists(macro_model_path) or not os.path.exists(move_model_path):
            raise FileNotFoundError(
                f"Trained models not found across {models_dir}. Please run train_ml_advanced.py and train_v22_pure_il.py first."
            )

        self.macro_features: list[str] = joblib.load(macro_feat_path)
        self.macro_model = xgb.XGBClassifier()
        self.macro_model.load_model(macro_model_path)

        self.move_features: list[str] = joblib.load(move_feat_path)
        self.move_model = xgb.XGBClassifier()
        self.move_model.load_model(move_model_path)

        self.switch_threshold = 0.5525
        if os.path.exists(threshold_path):
            try:
                with open(threshold_path) as f:
                    th_data = json.load(f)
                    self.switch_threshold = float(th_data.get("recommended_threshold", 0.5525))
            except Exception as e:
                print(f"[v22_pure_il] Warning loading threshold ({e}). Defaulting to {self.switch_threshold}")

        # Build normalized species lookup maps for macro model
        self._p1_species_norm_map: dict[str, str] = {}
        self._p2_species_norm_map: dict[str, str] = {}
        p1_prefix = "p1_active_pokemon_"
        p2_prefix = "p2_active_pokemon_"
        for col in self.macro_features:
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

        # Telemetry
        self._last_action_type: dict[str, int] = {}
        self._loop_guards_by_battle: dict[str, int] = {}
        self._xgb_switches_by_battle: dict[str, int] = {}
        self._xgb_stays_by_battle: dict[str, int] = {}
        self._xgb_prob_sum_by_battle: dict[str, float] = {}
        self._total_turns_by_battle: dict[str, int] = {}

    def reset_battles(self) -> None:
        """Clear both base tracking and custom ML telemetry dictionaries."""
        try:
            super().reset_battles()
        finally:
            self._last_action_type.clear()
            self._loop_guards_by_battle.clear()
            self._xgb_switches_by_battle.clear()
            self._xgb_stays_by_battle.clear()
            self._xgb_prob_sum_by_battle.clear()
            self._total_turns_by_battle.clear()

    def _build_empty_macro_features(self) -> dict[str, float]:
        return {col: 0.0 for col in self.macro_features}

    def _set_species_one_hot(self, features: dict[str, float], prefix: str, species: str | None) -> None:
        if not species:
            return
        norm_key = re.sub(r"[^a-z0-9]", "", str(species).lower())
        if prefix == "p1_active_pokemon" and norm_key in self._p1_species_norm_map:
            features[self._p1_species_norm_map[norm_key]] = 1.0
            return
        elif prefix == "p2_active_pokemon" and norm_key in self._p2_species_norm_map:
            features[self._p2_species_norm_map[norm_key]] = 1.0
            return
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

    def _extract_macro_features(self, battle, p1_override_species: str | None = None) -> pd.DataFrame:
        features = self._build_empty_macro_features()
        me = battle.active_pokemon
        opp = battle.opponent_active_pokemon

        if "turn_number" in features:
            features["turn_number"] = float(battle.turn)
        if "p1_hp_percent" in features:
            features["p1_hp_percent"] = float(me.current_hp_fraction) if me else 0.0
        if "p2_hp_percent" in features:
            features["p2_hp_percent"] = float(opp.current_hp_fraction) if opp else 0.0

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

        if "p1_tera_used" in features:
            features["p1_tera_used"] = 1.0 if not battle.can_tera else 0.0
        if "p2_tera_used" in features or "p2_used_tera" in features:
            opp_tera = getattr(battle, "opponent_can_tera", True)
            key = "p2_tera_used" if "p2_tera_used" in features else "p2_used_tera"
            features[key] = 0.0 if opp_tera else 1.0

        p1_spec = p1_override_species if p1_override_species else (str(me.species) if me else None)
        self._set_species_one_hot(features, "p1_active_pokemon", p1_spec)
        if opp:
            self._set_species_one_hot(features, "p2_active_pokemon", str(opp.species))

        return pd.DataFrame([features])

    def _choose_counterfactual_switch(self, battle):
        """Evaluate every candidate bench Pokémon using Counterfactual Stay Probability."""
        available = battle.available_switches or []
        if not available:
            return None
        if len(available) == 1:
            return available[0]

        best_candidate = None
        min_switch_prob = 2.0  # We want candidate with LOWEST switch-out probability (highest stay confidence)

        for candidate in available:
            df_feat = self._extract_macro_features(battle, p1_override_species=str(candidate.species))
            if "p1_hp_percent" in df_feat.columns:
                df_feat["p1_hp_percent"] = float(candidate.current_hp_fraction)
            prob_switch = float(self.macro_model.predict_proba(df_feat)[0][1])
            if prob_switch < min_switch_prob:
                min_switch_prob = prob_switch
                best_candidate = candidate

        return best_candidate or random.choice(available)

    def _choose_imitation_move(self, battle):
        """Evaluate available moves conditional on the exact active state."""
        moves = battle.available_moves or []
        if not moves:
            return None
        if len(moves) == 1:
            return moves[0]

        me = battle.active_pokemon
        opp = battle.opponent_active_pokemon

        turn_num = float(battle.turn)
        p1_hp = float(me.current_hp_fraction) if me else 0.0
        p2_hp = float(opp.current_hp_fraction) if opp else 0.0
        hp_diff = p1_hp - p2_hp
        haz_active = (
            1.0
            if (
                SideCondition.STEALTH_ROCK in battle.side_conditions
                or any(getattr(c, "name", str(c)) == "STEALTH_ROCK" for c in battle.side_conditions)
            )
            else 0.0
        )
        is_late = 1.0 if turn_num > 15 else 0.0

        best_move = None
        max_pref = -1.0

        for m in moves:
            # Check type multiplier directly from poke-env built-in type matrix
            eff = float(opp.damage_multiplier(m)) if opp else 1.0

            is_status = 1.0 if getattr(m.category, "name", str(m.category)) == "STATUS" else 0.0
            is_prio = 1.0 if getattr(m, "priority", 0) > 0 else 0.0
            is_stab = 1.0 if (me and m.type in getattr(me, "types", ())) else 0.0

            df_m = pd.DataFrame(
                [
                    {
                        "turn_number": turn_num,
                        "p1_hp_percent": p1_hp,
                        "p2_hp_percent": p2_hp,
                        "hp_diff": hp_diff,
                        "hazards_active": haz_active,
                        "is_late_game": is_late,
                        "move_base_power": float(m.base_power or 0),
                        "move_is_status": is_status,
                        "move_is_priority": is_prio,
                        "move_effectiveness": eff,
                        "move_is_stab": is_stab,
                    }
                ]
            )

            pref = float(self.move_model.predict_proba(df_m)[0][1])
            if pref > max_pref:
                max_pref = pref
                best_move = m

        return best_move or random.choice(moves)

    def _select_action(self, battle):
        btag = battle.battle_tag
        self._total_turns_by_battle[btag] = self._total_turns_by_battle.get(btag, 0) + 1

        me = battle.active_pokemon
        force_switch = battle.force_switch
        if isinstance(force_switch, list):
            force_switch = any(force_switch)

        if force_switch or me is None or me.fainted or not battle.available_moves:
            if battle.available_switches:
                best_sw = self._choose_counterfactual_switch(battle)
                if best_sw:
                    return self.create_order(best_sw)
            return None

        # 1. Macro Policy Prediction (Move vs Switch)
        live_feat = self._extract_macro_features(battle)
        probs = self.macro_model.predict_proba(live_feat)[0]
        action_type = 1 if len(probs) >= 2 and probs[1] >= self.switch_threshold else 0

        # Accumulate probability telemetry (mirrors v21 pattern)
        prob_val = float(probs[1]) if len(probs) >= 2 else 0.0
        self._xgb_prob_sum_by_battle[btag] = self._xgb_prob_sum_by_battle.get(btag, 0.0) + prob_val

        # Loop guard
        last_action = self._last_action_type.get(btag, 0)
        if action_type == 1 and last_action == 1 and battle.available_moves:
            self._loop_guards_by_battle[btag] = self._loop_guards_by_battle.get(btag, 0) + 1
            action_type = 0

        self._last_action_type[btag] = action_type
        if action_type == 1:
            self._xgb_switches_by_battle[btag] = self._xgb_switches_by_battle.get(btag, 0) + 1
        else:
            self._xgb_stays_by_battle[btag] = self._xgb_stays_by_battle.get(btag, 0) + 1

        # 2. Execute decision purely via ML models
        if action_type == 1 and battle.available_switches:
            best_sw = self._choose_counterfactual_switch(battle)
            if best_sw:
                return self.create_order(best_sw)

        best_m = self._choose_imitation_move(battle)
        if best_m:
            self._record_used_move(btag, best_m.id)
            tera = (
                battle.can_tera
                and me
                and best_m.type in getattr(me, "types", ())
                and best_m.base_power >= 80
                and me.current_hp_fraction > 0.4
            )
            return self.create_order(best_m, terastallize=tera)

        return self.choose_random_move(battle)


PureImitationAgent = HeuristicV22PureIL
