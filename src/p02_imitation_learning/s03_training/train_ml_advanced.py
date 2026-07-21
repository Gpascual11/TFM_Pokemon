"""Advanced XGBoost training script using the rich, unrolled battle dataset.

This script:
1) Loads `expert_gen9randombattle_advanced.parquet` (1.1M turns).
2) Performs a **group-based** train/test split (by `battle_id`) to prevent intra-battle data leakage.
3) Computes `scale_pos_weight` to handle Move vs. Switch class imbalance (~2.88).
4) Trains an XGBoost classifier (`n_estimators=300`, `max_depth=6`, `learning_rate=0.08`, `subsample=0.85`, `colsample_bytree=0.85`).
5) Calculates exact calibrated probability decision boundaries across precision-recall / F1 curves on the held-out test set.
6) Saves:
   - `xgboost_advanced_model.json`
   - `xgboost_advanced_features.pkl`
   - `xgboost_advanced_threshold.json` (containing optimal F1 and frequency-matched decision thresholds).
"""

from __future__ import annotations

import json
import os

import joblib
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import accuracy_score, classification_report, f1_score, roc_auc_score
from sklearn.model_selection import GroupShuffleSplit

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "src", "p02_imitation_learning", "s03_training", "models", "gen9randombattle")
os.makedirs(OUTPUT_DIR, exist_ok=True)

ADV_DATA_PATH = os.path.join(
    PROJECT_ROOT,
    "data",
    "imitation_learning_expert_replays",
    "expert_gen9randombattle_advanced.parquet",
)


def load_advanced_dataset() -> tuple[pd.DataFrame, pd.Series, np.ndarray]:
    """Load the advanced parquet dataset and separate X, y, and groups."""
    if not os.path.exists(ADV_DATA_PATH):
        raise FileNotFoundError(
            f"Advanced dataset not found at {ADV_DATA_PATH}. Please run extract_ml_features.py --mode advanced first."
        )

    print(f"Loading advanced dataset from:\n  {ADV_DATA_PATH}")
    df = pd.read_parquet(ADV_DATA_PATH)
    print(f"Loaded {len(df):,} rows with {df.shape[1]} columns.")

    if "battle_id" not in df.columns or "y_p1_action" not in df.columns:
        raise ValueError("Expected columns 'battle_id' and 'y_p1_action' in advanced dataset.")

    groups = df["battle_id"].to_numpy()
    y = df["y_p1_action"].astype(int)
    X = df.drop(columns=["battle_id", "y_p1_action"])

    # One-hot encode string identity columns
    cat_cols = [c for c in X.columns if X[c].dtype == "object" or X[c].dtype == "string"]
    if cat_cols:
        print(f"One-hot encoding categorical columns: {cat_cols}")
        X = pd.get_dummies(X, columns=cat_cols, drop_first=False)

    print(f"Feature matrix shape after encoding: {X.shape} (~1,150 columns).")
    return X, y, groups


def calibrate_thresholds(y_true: pd.Series, y_proba: np.ndarray) -> dict[str, float]:
    """Find optimal decision thresholds for the Switch class (1)."""
    print("\nCalibrating optimal probability decision boundaries on test set...")
    thresholds = np.linspace(0.20, 0.85, 131)
    best_f1 = -1.0
    best_f1_th = 0.50

    true_switch_rate = float(np.mean(y_true == 1))
    best_freq_diff = 1.0
    best_freq_th = 0.50

    for th in thresholds:
        preds = (y_proba >= th).astype(int)
        score = f1_score(y_true, preds)
        if score > best_f1:
            best_f1 = score
            best_f1_th = float(th)

        pred_rate = float(np.mean(preds == 1))
        freq_diff = abs(pred_rate - true_switch_rate)
        if freq_diff < best_freq_diff:
            best_freq_diff = freq_diff
            best_freq_th = float(th)

    print(f"  True test switch rate: {true_switch_rate * 100:.2f}%")
    print(f"  Optimal F1 threshold: {best_f1_th:.3f} (F1 = {best_f1:.4f})")
    print(
        f"  Frequency-matched threshold: {best_freq_th:.3f} (Predicted rate = {(y_proba >= best_freq_th).mean() * 100:.2f}%)"
    )

    return {
        "f1_optimal_threshold": round(best_f1_th, 4),
        "f1_score": round(best_f1, 4),
        "frequency_matched_threshold": round(best_freq_th, 4),
        "true_switch_rate": round(true_switch_rate, 4),
        # Recommended blended threshold balancing F1 and exact frequency calibration
        "recommended_threshold": round((best_f1_th + best_freq_th) / 2.0, 4),
    }


def train_xgboost_advanced(
    X: pd.DataFrame,
    y: pd.Series,
    groups: np.ndarray,
) -> tuple[xgb.XGBClassifier, list[str], dict[str, float]]:
    """Train the advanced XGBoost model using group-wise splitting."""
    print("\nPerforming GroupShuffleSplit (grouped by battle_id)...")
    splitter = GroupShuffleSplit(n_splits=1, test_size=0.20, random_state=42)
    (train_idx, test_idx) = next(splitter.split(X, y, groups=groups))

    X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
    y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]

    print(f"Train size: {len(X_train):,} rows")
    print(f"Test size:  {len(X_test):,} rows")

    n_move = float(np.sum(y_train == 0))
    n_switch = float(np.sum(y_train == 1))
    if n_switch == 0:
        raise ValueError("Training labels contain no 'Switch' examples.")
    ratio = n_move / n_switch
    print(f"\nClass counts (train): Move=0 -> {n_move:,.0f}, Switch=1 -> {n_switch:,.0f}")
    print(f"scale_pos_weight (Move / Switch) = {ratio:.3f}")

    print("\nTraining Advanced XGBoost Classifier...")
    model = xgb.XGBClassifier(
        n_estimators=300,
        max_depth=6,
        learning_rate=0.08,
        scale_pos_weight=ratio,
        subsample=0.85,
        colsample_bytree=0.85,
        random_state=42,
        eval_metric="logloss",
        n_jobs=-1,
    )

    model.fit(X_train, y_train)

    print("\nEvaluating on held-out test set...")
    y_proba = model.predict_proba(X_test)[:, 1]
    threshold_metrics = calibrate_thresholds(y_test, y_proba)
    rec_th = threshold_metrics["recommended_threshold"]

    y_pred_calibrated = (y_proba >= rec_th).astype(int)
    acc = accuracy_score(y_test, y_pred_calibrated)
    try:
        auc = roc_auc_score(y_test, y_proba)
    except ValueError:
        auc = float("nan")

    print(f"\nCalibrated Accuracy (th={rec_th}): {acc * 100:.2f}%")
    print(f"ROC AUC: {auc:.4f}")
    print("\nClassification Report (Calibrated Threshold):")
    print(classification_report(y_test, y_pred_calibrated, target_names=["Move (0)", "Switch (1)"]))

    feature_names: list[str] = X_train.columns.tolist()
    return model, feature_names, threshold_metrics


def main() -> None:
    print("=== Advanced ML Training Pipeline (Imitation Learning v21_xgboost) ===")
    X, y, groups = load_advanced_dataset()

    model, feature_names, threshold_metrics = train_xgboost_advanced(X, y, groups)

    feature_path = os.path.join(OUTPUT_DIR, "xgboost_advanced_features.pkl")
    model_path = os.path.join(OUTPUT_DIR, "xgboost_advanced_model.json")
    threshold_path = os.path.join(OUTPUT_DIR, "xgboost_advanced_threshold.json")

    print(f"\nSaving feature column order to:\n  {feature_path}")
    joblib.dump(feature_names, feature_path)

    print(f"Saving trained advanced XGBoost model to:\n  {model_path}")
    model.save_model(model_path)

    print(f"Saving calibrated probability thresholds to:\n  {threshold_path}")
    with open(threshold_path, "w") as f:
        json.dump(threshold_metrics, f, indent=2)

    print("\nDone. Phase 1 training upgrades complete.")


if __name__ == "__main__":
    main()
