from __future__ import annotations
import os
import random
import xgboost as xgb
import pandas as pd
from p01_heuristics.s01_singles.core.base import BaseHeuristic1v1

class MLBaselineAgent(BaseHeuristic1v1):
    """Imitation Learning Baseline Agent.
    
    This agent uses an XGBoost model trained on high-Elo human replays to decide
    whether to Attack or Switch based on 3 simple tabular features:
    1. HP Difference
    2. Presence of Hazards
    3. Time phase of the game (Late game vs Early game)
    
    If it decides to attack, it attacks randomly (since the model only predicts binary Action Type).
    If it decides to switch, it switches randomly.
    """
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.model = xgb.XGBClassifier()
        
        # Resolve the path to the trained JSON model
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../../"))
        model_path = os.path.join(project_root, "src/p03_ml_baseline/s03_training/models/ml_baseline.json")
        
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Trained ML model not found at {model_path}. Please run train_ml_baseline.py first.")
            
        self.model.load_model(model_path)

    def _extract_live_features(self, battle) -> pd.DataFrame:
        """
        Extracts the exact same features we used in training, but from the LIVE poke-env battle state!
        """
        me = battle.active_pokemon
        opp = battle.opponent_active_pokemon
        
        # 1. HP Difference
        my_hp_pct = me.current_hp_fraction * 100 if me else 100
        opp_hp_pct = opp.current_hp_fraction * 100 if opp else 100
        hp_diff = my_hp_pct - opp_hp_pct
        
        # 2. Hazards
        hazards_active = 1 if len(battle.side_conditions) > 0 else 0
        
        # 3. Late Game Time State
        is_late_game = 1 if battle.turn > 15 else 0
        
        # Return as a 1-row DataFrame so XGBoost can predict on it
        features = pd.DataFrame([{
            "hp_diff": hp_diff,
            "hazards_active": hazards_active,
            "is_late_game": is_late_game
        }])
        
        return features

    def _select_action(self, battle):
        if battle.active_pokemon is None or battle.opponent_active_pokemon is None:
             return self.choose_random_move(battle)

        my_moves = battle.available_moves
        my_switches = battle.available_switches
        
        # Fast exit if forced
        if not my_moves and my_switches:
            chosen = random.choice(my_switches)
            return self.create_order(chosen)
        elif my_moves and not my_switches:
            chosen = random.choice(my_moves)
            self._record_used_move(battle.battle_tag, chosen.id)
            return self.create_order(chosen)
        elif not my_moves and not my_switches:
             return self.choose_random_move(battle)

        # We have both choices. Ask the XGBoost Imitation model what a human would do!
        live_features = self._extract_live_features(battle)
        prediction = self.model.predict(live_features)[0]
        
        action_type = int(prediction) # 0 = Attack, 1 = Switch
        
        # Execute the model's policy
        if action_type == 1 and my_switches:
            chosen = random.choice(my_switches)
            return self.create_order(chosen)
        else:
            chosen = random.choice(my_moves)
            self._record_used_move(battle.battle_tag, chosen.id)
            return self.create_order(chosen)
