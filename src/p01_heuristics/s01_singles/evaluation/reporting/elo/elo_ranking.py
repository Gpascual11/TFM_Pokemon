import os
import glob
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import argparse
from sklearn.linear_model import LogisticRegression

def calculate_elo(df: pd.DataFrame, SCALE: int=400, BASE: int=10, INIT_RATING: int=1000):
    """
    Computes Bradley-Terry Whole-History Rating (Maximum Likelihood Estimation for Elo Ratings).
    Adapted from pokechamp's whr.py
    """
    if "model_a" not in df.columns or "model_b" not in df.columns or "winner" not in df.columns:
        raise ValueError("DataFrame must contain 'model_a', 'model_b', and 'winner' columns.")

    models = pd.concat([df['model_a'], df['model_b']]).unique()
    models_series = pd.Series(np.arange(len(models)), index=models)
    
    # duplicate battles to balance the dataset
    df_eval = pd.concat([df, df], ignore_index=True)
    
    p = len(models_series)
    n = df_eval.shape[0]

    X = np.zeros([n, p])
    X[np.arange(n), models_series[df_eval["model_a"]]] = +np.log(BASE)
    X[np.arange(n), models_series[df_eval["model_b"]]] = -np.log(BASE)

    # one A win => two A win (since we duplicated)
    Y = np.zeros(n)
    Y[df_eval["winner"] == "model_a"] = 1.0

    # Handle ties: one tie => one A win + one B win
    tie_idx = (df_eval["winner"] == "tie") | (df_eval["winner"] == "tie (bothbad)")
    # Split ties so exactly half are scored as a win for A
    tie_idx_subset = tie_idx.copy()
    tie_idx_subset[len(tie_idx)//2:] = False
    Y[tie_idx_subset] = 1.0

    lr = LogisticRegression(fit_intercept=False)
    lr.fit(X, Y)

    elo_scores = SCALE * lr.coef_[0] + INIT_RATING
    return pd.Series(elo_scores, index=models_series.index).sort_values(ascending=False)

def main():
    parser = argparse.ArgumentParser(description="Calculate Elo ratings from benchmark CSVs.")
    parser.add_argument("--data-dir", type=str, required=True, help="Path to CSV folder")
    parser.add_argument("--output", type=str, default=None, help="Output CSV file path. Defaults to elo_summary.csv in --data-dir.")
    args = parser.parse_args()

    if args.output is None:
        args.output = os.path.join(args.data_dir, "elo_summary.csv")

    print(f"📁 Loading benchmark files from: {args.data_dir}")
    csv_files = glob.glob(os.path.join(args.data_dir, "*.csv"))
    if not csv_files:
        print("❌ No CSV files found. Please ensure benchmarks have been run.")
        return
        
    all_battles = []
    
    for f in csv_files:
        try:
            df = pd.read_csv(f)
            # Standardize columns for names
            col_map = {
                "pokechamp_agent": "agent",
                "heuristic": "agent"
            }
            df = df.rename(columns=col_map)

            # Skip empty valid dataframes
            if df.empty or 'won' not in df.columns or 'agent' not in df.columns or 'opponent' not in df.columns:
                continue
                
            matchup_df = pd.DataFrame({
                'model_a': df['agent'],
                'model_b': df['opponent'],
                'winner': df['won'].apply(lambda w: 'model_a' if w == 1 else 'model_b')
            })
            all_battles.append(matchup_df)
        except Exception as e:
            print(f"Error reading {f}: {e}")
            
    if not all_battles:
        print("No valid battle records found.")
        return

    combined_df = pd.concat(all_battles, ignore_index=True)
    print(f"✅ Total battles loaded: {len(combined_df):,}")
    
    print("📈 Calculating Elo ratings...")
    elo_ratings = calculate_elo(combined_df)
    
    # Save the CSV
    elo_ratings_df = elo_ratings.reset_index()
    elo_ratings_df.columns = ["agent", "elo"]
    
    output_dir = os.path.dirname(args.output)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        
    elo_ratings_df.to_csv(args.output, index=False)
    print(f"💾 Saved Elo ratings to: {args.output}")

    print("\n--- Final Elo Ratings ---")
    print(elo_ratings)

if __name__ == "__main__":
    main()
