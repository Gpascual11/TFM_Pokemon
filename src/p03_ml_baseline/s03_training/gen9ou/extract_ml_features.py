import os
import re
import pandas as pd
from datasets import load_dataset
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../"))
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "src", "p03_ml_baseline/s03_training/models/gen9ou")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Important: ensure we point HuggingFace to the 1TB drive
hf_cache_dir = os.path.join(PROJECT_ROOT, "data", "huggingface_cache")
os.environ["HF_HOME"] = hf_cache_dir
os.environ["HF_DATASETS_CACHE"] = hf_cache_dir

# Import the dataset loader from pokechamp
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../../pokechamp/scripts/training")))
try:
    from dataset import load_filtered_dataset
except ImportError:
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../../../pokechamp/scripts/training")))
    from dataset import load_filtered_dataset

def extract_features_from_battles(dataset, max_battles=5000):
    """
    Parses raw Pokemon Showdown battle texts into tabular [X, y] for XGBoost Training.
    
    Features (X):
        - hp_advantage: (P1 HP% - P2 HP%) [Proxy extracted roughly from text]
        - hazards_active: (0 or 1)
        - is_late_game: (0 or 1 if turn > 15)
        
    Target (y):
        - action: 0 (Attack Move), 1 (Switch)
        
    Note for TFM: True imitation learning requires the actual Pokemon Showdown game engine 
    (like poke-env) to simulate state perfectly. Because generating engine states from text files
    is incredibly slow, this extracts a simplified NLP-based proxy state for demonstration 
    in the thesis.
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
        
        for turn_idx, turn_text in enumerate(turns[1:], 1):
            
            # --- FEATURE EXTRACTION (X) ---
            
            # 1. Update State (Hazards)
            if "|-sidestart|p1: Player 1|move: Stealth Rock" in turn_text:
                p1_hazards = True
            elif "|-sideend|p1: Player 1|move: Stealth Rock" in turn_text:
                p1_hazards = False
                
            # 2. Extract HP approximations (very rough regex matching the health bars e.g. 45/100)
            p1_hps = re.findall(r"p1[a-c]: [^\|]+\|(\d+)\/\d+", turn_text)
            p2_hps = re.findall(r"p2[a-c]: [^\|]+\|(\d+)\/\d+", turn_text)
            
            p1_hp_proxy = int(p1_hps[-1]) if p1_hps else 100
            p2_hp_proxy = int(p2_hps[-1]) if p2_hps else 100
            hp_diff = p1_hp_proxy - p2_hp_proxy
            
            # 3. Time state
            is_late_game = 1 if turn_idx > 15 else 0

            # --- TARGET EXTRACTION (y) ---
            
            p1_moves = len(re.findall(r"\|move\|p1[a-c]:", turn_text))
            p1_switches = len(re.findall(r"\|switch\|p1[a-c]:", turn_text))
            
            # Only record turns where P1 made a clear, single choice
            if p1_moves > 0 and p1_switches == 0: # Attack
                # Action = 0
                data_rows.append([hp_diff, int(p1_hazards), is_late_game, 0])
                
            elif p1_switches > 0 and p1_moves == 0: # Switch
                # Action = 1
                data_rows.append([hp_diff, int(p1_hazards), is_late_game, 1])

    columns = ["hp_diff", "hazards_active", "is_late_game", "action"]
    df = pd.DataFrame(data_rows, columns=columns)
    return df

def main():
    print("Loading Gen 9 OU Dataset from HuggingFace...")
    dataset = load_filtered_dataset(
        min_month="March2024",
        max_month="March2024",
        elo_ranges=["1800+"],
        split="train",
        gamemode="gen9ou" 
    )
    
    df = extract_features_from_battles(dataset, max_battles=10000)
    
    csv_path = os.path.join(OUTPUT_DIR, "ml_training_data.csv")
    df.to_csv(csv_path, index=False)
    
    print(f"Extracted {len(df)} feature vectors.")
    print(f"Saved dataset to {csv_path}")
    print("\nDataset Preview:")
    print(df.head())

if __name__ == "__main__":
    main()
