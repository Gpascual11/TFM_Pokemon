from __future__ import annotations

import os
import random

import joblib
import pandas as pd
import xgboost as xgb

from p01_heuristics.s01_singles.core.base import BaseHeuristic1v1
from p01_heuristics.s01_singles.core.common import calculate_base_damage, get_status_name


class MLAdvancedAgent(BaseHeuristic1v1):
    """Advanced Imitation Learning Agent.

    This agent uses the high-dimensional XGBoost model trained on the
    unrolled Gen9 Random Battle dataset (654 contextual features).

    Features include:
    - Turn number
    - Continuous HP tracking for both players
    - Stealth Rock and Tera usage flags
    - One-hot identity of active Pokémon for each side

    As with the baseline, the model predicts a binary action:
    - 0 = Use a Move
    - 1 = Switch Pokémon

    Once the action type is chosen, the specific move/switch is selected
    uniformly at random from the legal actions of that type.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Resolve artifacts saved by `train_ml_advanced.py`.
        # We mirror the same PROJECT_ROOT logic used in the training script
        # so that both components agree on where models live, regardless of
        # whether the project is executed from the repo root or installed
        # as a package.
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../"))
        models_dir = os.path.join(project_root, "src", "p03_ml_baseline", "s03_training", "models", "gen9random")

        feature_path = os.path.join(models_dir, "xgboost_advanced_features.pkl")
        model_path = os.path.join(models_dir, "xgboost_advanced_model.json")

        if not os.path.exists(feature_path):
            raise FileNotFoundError(
                f"Advanced feature list not found at {feature_path}. "
                "Please run train_ml_advanced.py first."
            )
        if not os.path.exists(model_path):
            raise FileNotFoundError(
                f"Advanced XGBoost model not found at {model_path}. "
                "Please run train_ml_advanced.py first."
            )

        self.feature_columns: list[str] = joblib.load(feature_path)
        self.model = xgb.XGBClassifier()
        self.model.load_model(model_path)

        # Track last action type to prevent infinite switching loops
        # 0 = Move, 1 = Switch
        self._last_action_type: dict[str, int] = {}

    def reset_battles(self) -> None:
        """Clear both the base battle history and our custom switch-loop tracking."""
        super().reset_battles()
        self._last_action_type.clear()
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
            features["p1_stealth_rock_active"] = 1.0 if "STEALTH_ROCK" in battle.side_conditions else 0.0
        if "p2_stealth_rock_active" in features:
            # For opponent side, poke-env uses opponent_side_conditions
            opp_conds = getattr(battle, "opponent_side_conditions", [])
            features["p2_stealth_rock_active"] = 1.0 if "STEALTH_ROCK" in opp_conds else 0.0

        # 4. Tera usage
        if "p1_tera_used" in features:
            # We assume Tera is used if the side can't Tera anymore
            features["p1_tera_used"] = 1.0 if not battle.can_tera else 0.0
        if "p2_tera_used" in features or "p2_used_tera" in features:
            # Note: poke-env's opponent tera tracking might be manual or through opponent_can_tera
            # For simplicity, we check if they've already used it once.
            opp_tera = getattr(battle, "opponent_can_tera", True)
            key = "p2_tera_used" if "p2_tera_used" in features else "p2_used_tera"
            features[key] = 0.0 if opp_tera else 1.0

        # 5. Species (One-hot)
        if me:
            self._set_species_one_hot(features, "p1_active_pokemon", str(me.species))
        if opp:
            self._set_species_one_hot(features, "p2_active_pokemon", str(opp.species))
        
        return pd.DataFrame([features])

    # --------------------------------------------------------------------- #
    # Decision Logic
    # --------------------------------------------------------------------- #
    def _select_action(self, battle):
        # Fallback for empty field
        if battle.active_pokemon is None or battle.opponent_active_pokemon is None:
            return None

        moves = battle.available_moves
        switches = battle.available_switches

        # Forced cases
        if not moves and switches:
            return self.create_order(random.choice(switches))
        if moves and not switches:
            return self.create_order(random.choice(moves))
        if not moves and not switches:
            return None

        # Decision Logic
        live_features = self._extract_live_features(battle)
        probs = self.model.predict_proba(live_features)[0]
        
        # Guard against zero-division or invalid probs
        if len(probs) < 2:
            action_type = 0
        else:
            # Shift towards Moves unless Switch is very likely
            action_type = 1 if probs[1] > 0.65 else 0
        
        battle_id = battle.battle_tag
        last_action = self._last_action_type.get(battle_id, 0)
        
        # --- INFINITE SWITCH LOOP GUARD ---
        # If we switched LAST turn, and we are not forced to switch (handled above),
        # force a move to prevent infinite team cycling.
        if action_type == 1 and last_action == 1 and moves:
             # print(f"[MLAdvanced] Game {battle_id} Turn {battle.turn}: Preventing Switch Loop. Forcing Move.")
             action_type = 0
            
        self._last_action_type[battle_id] = action_type

        # Execute decision
        if action_type == 1 and switches:
            return self.create_order(random.choice(switches))
        
        if moves:
            # Instead of random moves, use competitive damage logic (Heuristic V3)
            best_move = None
            max_damage = -1.0
            
            me = battle.active_pokemon
            opp = battle.opponent_active_pokemon
            my_status = get_status_name(me) if me else "HEALTHY"
            
            for move in moves:
                # Reuse core damage utility
                dmg = calculate_base_damage(move, me, opp, my_status)
                if dmg > max_damage:
                    max_damage, best_move = dmg, move
            
            if best_move:
                self._record_used_move(battle_id, best_move.id)
                return self.create_order(best_move)
            
            # Final fallback
            chosen = random.choice(moves)
            self._record_used_move(battle_id, chosen.id)
            return self.create_order(chosen)
            
        return None

