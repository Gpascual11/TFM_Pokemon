from __future__ import annotations

import argparse
import os

import matplotlib.pyplot as plt
import pandas as pd
import xgboost as xgb
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import GroupShuffleSplit

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))

def main():
    parser = argparse.ArgumentParser(description="Train XGBoost Imitation Learning Baseline Model")
    parser.add_argument("--format", type=str, default="gen9randombattle", help="Format/Gamemode model is trained on (default: gen9randombattle)")
    args = parser.parse_args()

    output_dir = os.path.join(PROJECT_ROOT, "src", f"p02_imitation_learning/s03_training/models/{args.format}")
    os.makedirs(output_dir, exist_ok=True)

    print("Loading extracted ML features...")
    data_path = os.path.join(output_dir, "ml_training_data.csv")
    
    if not os.path.exists(data_path):
        print(f"File not found: {data_path}")
        print("Please run extract_ml_features.py first.")
        return

    df = pd.read_csv(data_path)
    print(f"Loaded {len(df)} samples.")
    
    # 1. Prepare Data
    if "battle_id" not in df.columns:
        print("Error: 'battle_id' column not found in training data. Please run extract_ml_features.py again.")
        return
        
    groups = df["battle_id"]
    X = df.drop(columns=["battle_id", "action"])
    y = df["action"] # 0 = Move, 1 = Switch
    
    # Perform a group-based train/test split to avoid temporal leakage between turns of the same battle.
    splitter = GroupShuffleSplit(n_splits=1, test_size=0.20, random_state=42)
    train_idx, test_idx = next(splitter.split(X, y, groups=groups))
    
    X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
    y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]
    
    # 2. Train XGBoost Model
    print("\nTraining XGBoost Classifier (with GroupShuffleSplit)...")
    model = xgb.XGBClassifier(
        n_estimators=100,
        max_depth=4,
        learning_rate=0.1,
        random_state=42,
        use_label_encoder=False,
        eval_metric='logloss'
    )
    
    model.fit(X_train, y_train)
    
    # 3. Evaluate
    y_pred = model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    print(f"\nModel Accuracy on Test Set: {accuracy * 100:.2f}%")
    print(classification_report(y_test, y_pred, target_names=["Attack (0)", "Switch (1)"]))
    
    # 4. Feature Importance
    print("\nPlotting Feature Importance...")
    plt.figure(figsize=(10, 6))
    xgb.plot_importance(model, max_num_features=10)
    plt.title("XGBoost Feature Importance (F-Score)")
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "feature_importance.png"))
    plt.close()
    
    # 5. Save Model
    model_path = os.path.join(output_dir, "ml_baseline.json")
    model.save_model(model_path)
    print(f"Saved trained XGBoost model to {model_path}")
    print("Next step: Create the ml_baseline.py agent to load this .json file and play Showdown!")

if __name__ == "__main__":
    main()
