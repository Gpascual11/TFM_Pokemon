from __future__ import annotations

import os

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
    """Advanced Imitation Learning Agent (v21_xgboost).

    This agent uses the high-dimensional XGBoost model trained on the
    unrolled Gen9 Random Battle dataset (654 contextual features).

    Features include:
    - Turn number
    - Continuous HP tracking for both players
    - Stealth Rock and Tera usage flags
    - One-hot identity of active Pokémon for each side

    The model predicts a binary action:
    - 0 = Use a Move
    - 1 = Switch Pokémon

    Once the action type is chosen, it is executed using HeuristicV14's
    exact damage calculations, move scoring, and switch scoring instead
    of random selection.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Resolve artifacts saved by `train_ml_advanced.py`.
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
        models_dir = os.path.join(
            project_root, "src", "p02_imitation_learning", "s03_training", "models", "gen9randombattle"
        )

        feature_path = os.path.join(models_dir, "xgboost_advanced_features.pkl")
        model_path = os.path.join(models_dir, "xgboost_advanced_model.json")

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

        # Track last action type to prevent infinite switching loops
        # 0 = Move, 1 = Switch
        self._last_action_type: dict[str, int] = {}
        # Advanced metrics tracking
        self._ko_guards_by_battle: dict[str, int] = {}
        self._loop_guards_by_battle: dict[str, int] = {}
        self._xgb_switches_by_battle: dict[str, int] = {}
        self._xgb_stays_by_battle: dict[str, int] = {}
        self._xgb_prob_sum_by_battle: dict[str, float] = {}
        self._endgame_solves_by_battle: dict[str, int] = {}
        self._total_turns_by_battle: dict[str, int] = {}

    def reset_battles(self) -> None:
        """Clear both the base battle history and our custom switch-loop tracking."""
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
        """Activate the correct one-hot column for the given species.

        Poke-env IDs (e.g., 'ironvaliant') differ from Showdown logs (e.g., 'iron valiant').
        We attempt multiple formats to match the model's schema.
        """
        if not species:
            return

        # Paradox + Regional candidates
        species_raw = str(species).lower()
        candidates = [
            f"{prefix}_{species_raw}",
            f"{prefix}_{species_raw.replace('-', ' ')}",
            f"{prefix}_{species_raw.replace('_', ' ')}",
            # Paradox mapping (e.g. 'ironvaliant' -> 'iron valiant')
            f"{prefix}_{species_raw.replace('iron', 'iron ')}",
            f"{prefix}_{species_raw.replace('great', 'great ')}",
            f"{prefix}_{species_raw.replace('roaring', 'roaring ')}",
            f"{prefix}_{species_raw.replace('walking', 'walking ')}",
            f"{prefix}_{species_raw.replace('brute', 'brute ')}",
            f"{prefix}_{species_raw.replace('flutter', 'flutter ')}",
            f"{prefix}_{species_raw.replace('scream', 'scream ')}",
            f"{prefix}_{species_raw.replace('slither', 'slither ')}",
            f"{prefix}_{species_raw.replace('ironmoth', 'iron moth')}",
            f"{prefix}_{species_raw.replace('greattusk', 'great tusk')}",
            f"{prefix}_{species_raw.replace('ironvaliant', 'iron valiant')}",
            f"{prefix}_{species_raw.replace('walkingwake', 'walking wake')}",
            f"{prefix}_{species_raw.replace('roaringmoon', 'roaring moon')}",
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

        # 2. Continuous HP (0.0 to 1.0)
        if "p1_hp_percent" in features:
            features["p1_hp_percent"] = float(me.current_hp_fraction) if me else 0.0
        if "p2_hp_percent" in features:
            features["p2_hp_percent"] = float(opp.current_hp_fraction) if opp else 0.0

        # 3. Stealth Rock state
        if "p1_stealth_rock_active" in features:
            features["p1_stealth_rock_active"] = 1.0 if (SideCondition.STEALTH_ROCK in battle.side_conditions or any(getattr(c, "name", str(c)) == "STEALTH_ROCK" for c in battle.side_conditions)) else 0.0
        if "p2_stealth_rock_active" in features:
            opp_conds = getattr(battle, "opponent_side_conditions", {}) or {}
            features["p2_stealth_rock_active"] = 1.0 if (SideCondition.STEALTH_ROCK in opp_conds or any(getattr(c, "name", str(c)) == "STEALTH_ROCK" for c in opp_conds)) else 0.0

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

        # Initialize tracking for this battle tag
        self._ko_guards_by_battle.setdefault(btag, 0)
        self._loop_guards_by_battle.setdefault(btag, 0)
        self._xgb_switches_by_battle.setdefault(btag, 0)
        self._xgb_stays_by_battle.setdefault(btag, 0)
        self._xgb_prob_sum_by_battle.setdefault(btag, 0.0)
        self._endgame_solves_by_battle.setdefault(btag, 0)
        self._total_turns_by_battle[btag] = self._total_turns_by_battle.get(btag, 0) + 1

        # 1. Update roles and parse battlefield states
        self._evaluate_team_roles(battle)
        self._update_inferences(battle)

        # Fainted Switch / Forced Switch / No Available Moves
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
            return None

        # 2. Guaranteed KO — always take the kill immediately.
        format_str = battle._format or ""
        my_status = get_status_name(me)
        opp_status = get_status_name(opp)
        my_speed = self._get_boosted_speed(me, my_status, format_str)
        opp_speed = self._get_boosted_speed(opp, opp_status, format_str)

        ko_move = self._find_guaranteed_ko(battle, me, opp, my_speed, opp_speed)
        if ko_move:
            self._ko_guards_by_battle[btag] = self._ko_guards_by_battle.get(btag, 0) + 1
            self._record_used_move(btag, ko_move.id)
            tera = self._should_terastallize(battle, ko_move)
            return self.create_order(ko_move, terastallize=tera)

        # 3. XGBoost Action Type prediction (0 = Move, 1 = Switch)
        live_features = self._extract_live_features(battle)
        probs = self.model.predict_proba(live_features)[0]

        if len(probs) < 2:
            action_type = 0
            prob_val = 0.0
        else:
            action_type = 1 if probs[1] > 0.65 else 0
            prob_val = float(probs[1])

        self._xgb_prob_sum_by_battle[btag] = self._xgb_prob_sum_by_battle.get(btag, 0.0) + prob_val

        # Record XGBoost high-level policy decision
        if action_type == 1:
            self._xgb_switches_by_battle[btag] = self._xgb_switches_by_battle.get(btag, 0) + 1
        else:
            self._xgb_stays_by_battle[btag] = self._xgb_stays_by_battle.get(btag, 0) + 1

        # --- INFINITE SWITCH LOOP GUARD ---
        # If we switched LAST turn, and we are not forced to switch (handled above),
        # force a move to prevent infinite team cycling.
        last_action = self._last_action_type.get(btag, 0)
        if action_type == 1 and last_action == 1 and battle.available_moves:
            self._loop_guards_by_battle[btag] = self._loop_guards_by_battle.get(btag, 0) + 1
            action_type = 0

        self._last_action_type[btag] = action_type

        # 4. Execute Decision
        if action_type == 1 and battle.available_switches:
            # Switch action chosen: use V14's best switch evaluator
            switch = self._get_best_switch(battle, opp)
            if switch:
                return self.create_order(switch)

        # Move action chosen (or fallback if no switch was found/valid)
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

        if best_move:
            self._record_used_move(btag, best_move.id)
            tera = self._should_terastallize(battle, best_move)
            return self.create_order(best_move, terastallize=tera)

        return self.choose_random_move(battle)


# Backward compatibility alias for training scripts
MLAdvancedAgent = HeuristicV21XGBoost
