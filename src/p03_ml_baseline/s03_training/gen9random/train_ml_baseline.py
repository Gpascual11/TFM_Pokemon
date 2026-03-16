# Python Script Version of the XGBoost baseline notebook
from __future__ import annotations
import os
import pandas as pd
import matplotlib.pyplot as plt
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../"))
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "src/p03_ml_baseline/s03_training/models/gen9random")

def main():
    print("Loading extracted ML features...")
    data_path = os.path.join(OUTPUT_DIR, "ml_training_data.csv")
    
    if not os.path.exists(data_path):
        print(f"File not found: {data_path}")
        print("Please run extract_ml_features.py first.")
        return

    df = pd.read_csv(data_path)
    print(f"Loaded {len(df)} samples.")
    
    # 1. Prepare Data
    X = df.drop("action", axis=1)
    y = df["action"] # 0 = Move, 1 = Switch
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    # 2. Train XGBoost Model
    print("\nTraining XGBoost Classifier...")
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
    plt.savefig(os.path.join(OUTPUT_DIR, "feature_importance.png"))
    plt.close()
    
    # 5. Save Model
    model_path = os.path.join(OUTPUT_DIR, "ml_baseline.json")
    model.save_model(model_path)
    print(f"Saved trained XGBoost model to {model_path}")
    print("Next step: Create the ml_baseline.py agent to load this .json file and play Showdown!")

if __name__ == "__main__":
    main()
