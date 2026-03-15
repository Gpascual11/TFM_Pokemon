import os
import glob
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sklearn.linear_model import LogisticRegression

# Define paths for Data input and Plot output
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../../"))
BENCHMARKS_DIR = os.path.join(PROJECT_ROOT, "data/1_vs_1/benchmarks/unified")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "src/p01_heuristics/s01_singles/evaluation/results")
os.makedirs(OUTPUT_DIR, exist_ok=True)

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
    print(f"Loading benchmark files from: {BENCHMARKS_DIR}")
    csv_files = glob.glob(os.path.join(BENCHMARKS_DIR, "*.csv"))
    if not csv_files:
        print("No CSSV files found. Please ensure benchmarks have been run.")
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
                'winner': df['won'].apply(lambda w: 'model_a' if w == 1 else 'model_b') # ignoring ties for simple benchmark processing unless recorded otherwise
            })
            all_battles.append(matchup_df)
        except Exception as e:
            print(f"Error reading {f}: {e}")
            
    if not all_battles:
        print("No valid battle records found.")
        return

    combined_df = pd.concat(all_battles, ignore_index=True)
    print(f"Total battles loaded: {len(combined_df)}")
    
    print("Calculating Elo ratings...")
    elo_ratings = calculate_elo(combined_df)
    
    print("\n--- Final Elo Ratings ---")
    print(elo_ratings)
    
    # Save the text file
    output_txt = os.path.join(OUTPUT_DIR, "elo_ratings.txt")
    with open(output_txt, "w") as f:
        f.write("Final Elo Ratings\n")
        f.write("=================\n")
        f.write(elo_ratings.to_string())
    print(f"\nSaved ratings text to {output_txt}")

    # Generate a plot
    plt.figure(figsize=(10, 6))
    elo_ratings.plot(kind='bar', color='skyblue', edgecolor='black')
    plt.title('Agent Elo Ratings (Bradley-Terry WHR)')
    plt.xlabel('Agent')
    plt.ylabel('Elo Rating (Baseline = 1000)')
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    
    output_png = os.path.join(OUTPUT_DIR, "elo_ratings_plot.png")
    plt.savefig(output_png)
    print(f"Saved ratings plot to {output_png}")

if __name__ == "__main__":
    main()
