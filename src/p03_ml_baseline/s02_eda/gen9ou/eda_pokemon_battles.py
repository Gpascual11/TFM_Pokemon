import os
import re
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datasets import load_dataset
# Import the dataset loader from pokechamp
import sys
# The current file is in src/p03_ml_baseline/s02_eda/gen9ou/eda_pokemon_battles.py
# We need to reach pokechamp/scripts/training/
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../pokechamp/scripts/training")))
try:
    from dataset import load_filtered_dataset
except ImportError:
    # Try one level higher just in case
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../../pokechamp/scripts/training")))
    from dataset import load_filtered_dataset


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../"))
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "src/p03_ml_baseline/s02_eda/plots/gen9ou")
os.makedirs(OUTPUT_DIR, exist_ok=True)

def parse_battle_logs(dataset, max_battles=1000):
    """
    Parses raw Pokemon Showdown battle texts into a structured DataFrame.
    This extracts the basic Move vs Switch distribution.
    """
    actions = []
    
    print(f"Parsing up to {max_battles} battles...")
    
    for i, example in enumerate(dataset):
        if i >= max_battles:
            break
            
        text = example['text']
        # Very basic regex to split by turns
        turns = text.split("|turn|")
        
        for turn_idx, turn_text in enumerate(turns[1:], 1): # Skip turn 0 (lead selection)
            # Find what Player 1 and Player 2 did
            # |move|p1a: Pokemon|Move Name
            # |switch|p1a: Pokemon|New Pokemon
            
            p1_moves = len(re.findall(r"\|move\|p1[a-c]:", turn_text))
            p2_moves = len(re.findall(r"\|move\|p2[a-c]:", turn_text))
            
            p1_switches = len(re.findall(r"\|switch\|p1[a-c]:", turn_text))
            p2_switches = len(re.findall(r"\|switch\|p2[a-c]:", turn_text))
            
            # Check for hazards
            stealth_rock = "|-sidestart|p1: Player 1|move: Stealth Rock" in text[:text.find(turn_text)]
            
            # Record actions for P1
            if p1_moves > 0:
                actions.append({"player": "p1", "turn": turn_idx, "action_type": "move", "hazards_up": stealth_rock, "elo": example["elo"]})
            elif p1_switches > 0:
                actions.append({"player": "p1", "turn": turn_idx, "action_type": "switch", "hazards_up": stealth_rock, "elo": example["elo"]})
                
            # Record actions for P2 (simplified hazard check)
            if p2_moves > 0:
                actions.append({"player": "p2", "turn": turn_idx, "action_type": "move", "hazards_up": False, "elo": example["elo"]})
            elif p2_switches > 0:
                actions.append({"player": "p2", "turn": turn_idx, "action_type": "switch", "hazards_up": False, "elo": example["elo"]})

    df = pd.DataFrame(actions)
    return df

def generate_eda_plots(df):
    """
    Generates plots for the TFM based on the structured DataFrame.
    """
    print("Generating plots...")
    
    # 1. Overall Action Distribution
    plt.figure(figsize=(8, 6))
    sns.countplot(x="action_type", data=df, palette="Set2")
    plt.title("Overall Action Distribution (Move vs Switch)")
    plt.xlabel("Action Type")
    plt.ylabel("Frequency")
    plt.savefig(os.path.join(OUTPUT_DIR, "action_distribution.png"))
    plt.close()
    
    # 2. Action Type over Turns (Are switches more common early game?)
    plt.figure(figsize=(12, 6))
    
    # Bucket turns into early (1-5), mid (6-15), late (15+)
    def categorize_turn(t):
        if t <= 5: return "Early (1-5)"
        elif t <= 15: return "Mid (6-15)"
        else: return "Late (16+)"
        
    df['turn_phase'] = df['turn'].apply(categorize_turn)
    
    sns.countplot(x="turn_phase", hue="action_type", data=df, palette="Set2", 
                  order=["Early (1-5)", "Mid (6-15)", "Late (16+)"])
    plt.title("Action Types by Game Phase")
    plt.xlabel("Phase of Game")
    plt.ylabel("Frequency")
    plt.savefig(os.path.join(OUTPUT_DIR, "actions_by_phase.png"))
    plt.close()
    
    # 3. Does Stealth Rock reduce switching?
    plt.figure(figsize=(8, 6))
    p1_df = df[df['player'] == 'p1'] # Only look at P1 where we tracked hazards
    if not p1_df.empty:
        switch_rates = p1_df.groupby('hazards_up')['action_type'].value_counts(normalize=True).unstack()
        if 'switch' in switch_rates.columns:
            switch_rates[['switch']].plot(kind='bar', color='salmon', edgecolor='black', figsize=(8,6))
            plt.title("Switch Rate depending on Hazard Presence")
            plt.xlabel("Hazards Present")
            plt.ylabel("Percentage of actions that are Switches")
            plt.xticks([0, 1], ['No Hazards', 'Hazards Active'], rotation=0)
            plt.savefig(os.path.join(OUTPUT_DIR, "hazard_switching_correlation.png"))
            plt.close()

def main():
    print("Configuring HuggingFace cache to use the TFM/data/ directory...")
    # The user has a 1TB drive mounted/linked at TFM/data/, so we save the multi-gigabyte files there.
    hf_cache_dir = os.path.join(PROJECT_ROOT, "data", "huggingface_cache")
    os.makedirs(hf_cache_dir, exist_ok=True)
    os.environ["HF_DATASETS_CACHE"] = hf_cache_dir

    print("Loading Gen 9 OU Dataset from HuggingFace...")
    # Load a small slice of Gen 9 Random Battle High Elo
    dataset = load_filtered_dataset(
        min_month="March2024",
        max_month="March2024",
        elo_ranges=["1800+"],
        split="train",
        gamemode="gen9ou" 
    )
    
    df = parse_battle_logs(dataset, max_battles=5000)
    
    print(f"Extracted {len(df)} discrete actions.")
    
    if len(df) > 0:
        generate_eda_plots(df)
        print(f"EDA Complete! Plots saved to {OUTPUT_DIR}")
        
    # Save the raw dataframe for inspecting if needed
    df.to_csv(os.path.join(OUTPUT_DIR, "extracted_actions.csv"), index=False)

if __name__ == "__main__":
    main()
