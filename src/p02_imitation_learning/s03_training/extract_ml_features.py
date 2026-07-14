import argparse
import os
import re
import sys

import pandas as pd

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))

# Important: ensure we point HuggingFace to the 1TB drive
hf_cache_dir = os.path.join(PROJECT_ROOT, "data", "huggingface_cache")
os.environ["HF_HOME"] = hf_cache_dir
os.environ["HF_DATASETS_CACHE"] = hf_cache_dir

# Import the dataset loader from pokechamp
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../pokechamp/scripts/training")))
try:
    from dataset import load_filtered_dataset
except ImportError:
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../pokechamp/scripts/training")))
    from dataset import load_filtered_dataset

def extract_features_from_battles(dataset, max_battles=5000):
    """
    Parses raw Pokemon Showdown battle texts into tabular [X, y] for XGBoost Training.
    
    Features (X):
        - hp_diff: (P1 HP% - P2 HP%)
        - hazards_active: (0 or 1)
        - is_late_game: (0 or 1 if turn > 15)
        
    Target (y):
        - action: 0 (Attack Move), 1 (Switch)
    """
    data_rows = []
    
    print(f"Extracting Tabular Features from {max_battles} battles...")
    
    for i, example in enumerate(dataset):
        if i >= max_battles:
            break
            
        text = example['text']
        turns = text.split("|turn|")
        
        # State tracking through the text
        p1_hazards = False
        p1_hp_pct = 100.0
        p2_hp_pct = 100.0
        
        for turn_idx, turn_text in enumerate(turns[1:], 1):
            
            # --- FEATURE EXTRACTION (X) ---
            
            # 1. Update State (Hazards)
            if "|-sidestart|p1: Player 1|move: Stealth Rock" in turn_text:
                p1_hazards = True
            elif "|-sideend|p1: Player 1|move: Stealth Rock" in turn_text:
                p1_hazards = False
                
            # 2. Extract HP percentages using HP/MaxHP ratio
            p1_hps = re.findall(r"p1[a-c]: [^\|]+\|(\d+)\/(\d+)", turn_text)
            p2_hps = re.findall(r"p2[a-c]: [^\|]+\|(\d+)\/(\d+)", turn_text)
            
            if p1_hps and float(p1_hps[-1][1]) > 0:
                p1_hp_pct = float(p1_hps[-1][0]) / float(p1_hps[-1][1]) * 100
            if p2_hps and float(p2_hps[-1][1]) > 0:
                p2_hp_pct = float(p2_hps[-1][0]) / float(p2_hps[-1][1]) * 100
            hp_diff = p1_hp_pct - p2_hp_pct
            
            # 3. Time state
            is_late_game = 1 if turn_idx > 15 else 0

            # --- TARGET EXTRACTION (y) ---
            
            p1_moves = len(re.findall(r"\|move\|p1[a-c]:", turn_text))
            p1_switches = len(re.findall(r"\|switch\|p1[a-c]:", turn_text))
            
            # Only record turns where P1 made a clear, single choice
            if p1_moves > 0 and p1_switches == 0: # Attack
                # Action = 0
                data_rows.append([example['battle_id'], hp_diff, int(p1_hazards), is_late_game, 0])
                
            elif p1_switches > 0 and p1_moves == 0: # Switch
                # Action = 1
                data_rows.append([example['battle_id'], hp_diff, int(p1_hazards), is_late_game, 1])

    columns = ["battle_id", "hp_diff", "hazards_active", "is_late_game", "action"]
    df = pd.DataFrame(data_rows, columns=columns)
    return df

def normalize_month_year(val: str) -> str:
    """Normalize YYYY-MM formatted date to MonthYear (e.g. 2025-01 -> January2025)."""
    if not val:
        return val
    if re.match(r'^\d{4}-\d{2}$', val):
        year, month = val.split('-')
        month_map = {
            1: "January", 2: "February", 3: "March", 4: "April", 5: "May", 6: "June",
            7: "July", 8: "August", 9: "September", 10: "October", 11: "November", 12: "December"
        }
        try:
            month_int = int(month)
            if month_int in month_map:
                return f"{month_map[month_int]}{year}"
        except ValueError:
            pass
    return val

def main():
    parser = argparse.ArgumentParser(description="Extract Features from Replay Dataset")
    parser.add_argument("--format", type=str, default="gen9randombattle", help="Format/Gamemode to load (default: gen9randombattle)")
    parser.add_argument("--start", type=str, default="August2023", help="Start month (default: August2023)")
    parser.add_argument("--end", type=str, default="March2025", help="End month (default: March2025)")
    parser.add_argument("--max-battles", type=int, default=10000, help="Max battles to process (default: 10000)")
    args = parser.parse_args()

    start_normalized = normalize_month_year(args.start)
    end_normalized = normalize_month_year(args.end)

    output_dir = os.path.join(PROJECT_ROOT, "src", f"p02_imitation_learning/s03_training/models/{args.format}")
    os.makedirs(output_dir, exist_ok=True)

    print(f"Loading {args.format} Dataset from HuggingFace cache...")
    dataset = load_filtered_dataset(
        min_month=start_normalized,
        max_month=end_normalized,
        elo_ranges=["1800+"],
        split="train",
        gamemode=args.format
    )
    
    df = extract_features_from_battles(dataset, max_battles=args.max_battles)
    
    csv_path = os.path.join(output_dir, "ml_training_data.csv")
    df.to_csv(csv_path, index=False)
    
    print(f"Extracted {len(df)} feature vectors.")
    print(f"Saved dataset to {csv_path}")
    print("\nDataset Preview:")
    print(df.head())

if __name__ == "__main__":
    main()
