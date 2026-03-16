from __future__ import annotations

"""
Advanced XGBoost training script using the rich, unrolled battle dataset.

This script assumes that the advanced tabular dataset has already been
materialized to a parquet file with the following columns:

- battle_id:   Unique identifier per battle (used for GroupShuffleSplit only).
- y_p1_action: Target label (0 = Move, 1 = Switch).
- 654 feature columns matching the advanced EDA (turn/HP/hazards/OHE species).

It:
1) Loads the parquet dataset.
2) Performs a **group-based** train/test split to avoid temporal leakage
   between turns of the same battle.
3) Computes `scale_pos_weight` to rebalance the minority "Switch" class.
4) Trains an XGBoost classifier with the tuned hyperparameters from the
   advanced notebook.
5) Saves:
   - The trained model to `xgboost_advanced_model.json`
   - The exact feature column order to `xgboost_advanced_features.pkl`
"""

import os
from typing import List

import joblib
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import accuracy_score, classification_report, roc_auc_score
from sklearn.model_selection import GroupShuffleSplit


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../"))
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "src", "p03_ml_baseline", "s03_training", "models", "gen9random")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Path to the advanced, unrolled dataset produced by the EDA pipeline
ADV_DATA_PATH = os.path.join(
    PROJECT_ROOT,
    "data",
    "models",
    "dataset",
    "processed",
    "expert_gen9randombattle_advanced.parquet",
)


def load_advanced_dataset() -> tuple[pd.DataFrame, pd.Series, np.ndarray]:
    """Load the advanced parquet dataset and separate X, y, and groups.

    The raw parquet currently contains a compact schema with:
    - Numeric context features (turn, HP, hazards, tera, etc.)
    - String identity columns for the active Pokémon on each side
      (e.g. 'p1_active_pokemon', 'p2_active_pokemon').

    We expand any string/object columns into one-hot encodings so that the
    resulting matrix is purely numeric and compatible with XGBoost, while
    matching the 654-dimensional design from the notebook.
    """
    if not os.path.exists(ADV_DATA_PATH):
        raise FileNotFoundError(
            f"Advanced dataset not found at {ADV_DATA_PATH}. "
            "Please generate `expert_gen9ou_advanced.parquet` from the EDA pipeline first."
        )

    print(f"Loading advanced dataset from:\n  {ADV_DATA_PATH}")
    df = pd.read_parquet(ADV_DATA_PATH)
    print(f"Loaded {len(df)} rows with {df.shape[1]} columns.")

    if "battle_id" not in df.columns or "y_p1_action" not in df.columns:
        raise ValueError(
            "Expected columns 'battle_id' and 'y_p1_action' to be present in the advanced dataset."
        )

    groups = df["battle_id"].to_numpy()
    y = df["y_p1_action"].astype(int)

    # Drop non-feature columns
    X = df.drop(columns=["battle_id", "y_p1_action"])

    # Identify categorical/string columns to one-hot encode
    cat_cols = [c for c in X.columns if X[c].dtype == "object" or X[c].dtype == "string"]
    if cat_cols:
        print(f"One-hot encoding categorical columns: {cat_cols}")
        X = pd.get_dummies(X, columns=cat_cols, drop_first=False)

    print(f"Feature matrix shape after encoding: {X.shape} (target ≈ 654 columns).")
    return X, y, groups


def train_xgboost_advanced(
    X: pd.DataFrame,
    y: pd.Series,
    groups: np.ndarray,
) -> tuple[xgb.XGBClassifier, List[str]]:
    """Train the advanced XGBoost model using group-wise splitting."""
    print("\nPerforming GroupShuffleSplit (grouped by battle_id)...")
    splitter = GroupShuffleSplit(n_splits=1, test_size=0.20, random_state=42)
    (train_idx, test_idx) = next(splitter.split(X, y, groups=groups))

    X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
    y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]

    print(f"Train size: {len(X_train)} rows")
    print(f"Test size:  {len(X_test)} rows")

    # Compute class imbalance ratio for scale_pos_weight (Move=0, Switch=1)
    n_move = float(np.sum(y_train == 0))
    n_switch = float(np.sum(y_train == 1))
    if n_switch == 0:
        raise ValueError("Training labels contain no 'Switch' examples (class 1).")
    ratio = n_move / n_switch
    print(f"\nClass counts (train): Move=0 -> {n_move:.0f}, Switch=1 -> {n_switch:.0f}")
    print(f"scale_pos_weight (Move / Switch) = {ratio:.3f}")

    print("\nTraining Advanced XGBoost Classifier...")
    model = xgb.XGBClassifier(
        n_estimators=200,
        max_depth=6,
        learning_rate=0.1,
        scale_pos_weight=ratio,
        random_state=42,
        eval_metric="logloss",
        n_jobs=-1,
    )

    model.fit(X_train, y_train)

    print("\nEvaluating on held-out test set...")
    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]

    acc = accuracy_score(y_test, y_pred)
    try:
        auc = roc_auc_score(y_test, y_proba)
    except ValueError:
        auc = float("nan")

    print(f"Accuracy: {acc * 100:.2f}%")
    print(f"ROC AUC: {auc:.3f}")
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred, target_names=["Move (0)", "Switch (1)"]))

    feature_names: List[str] = X_train.columns.tolist()
    return model, feature_names


def main() -> None:
    print("=== Advanced ML Baseline Training (Imitation Learning) ===")
    X, y, groups = load_advanced_dataset()

    model, feature_names = train_xgboost_advanced(X, y, groups)

    # Persist artifacts in the same models directory used by the baseline
    feature_path = os.path.join(OUTPUT_DIR, "xgboost_advanced_features.pkl")
    model_path = os.path.join(OUTPUT_DIR, "xgboost_advanced_model.json")

    print(f"\nSaving feature column order to:\n  {feature_path}")
    joblib.dump(feature_names, feature_path)

    print(f"Saving trained advanced XGBoost model to:\n  {model_path}")
    model.save_model(model_path)

    print("\nDone. You can now use MLAdvancedAgent to play live battles using this model.")


if __name__ == "__main__":
    main()

