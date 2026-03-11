import os
import sys
import argparse

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
    # Handle cases where path might be different based on execution context
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../pokechamp/scripts/training")))
    from dataset import load_filtered_dataset

def main():
    parser = argparse.ArgumentParser(description="Download Pokemon Replay Dataset with Smart Caching")
    parser.add_argument("--gamemode", type=str, default="gen9ou", help="Game mode (e.g. gen9ou, gen8ou, gen9vgc2024regg)")
    parser.add_argument("--start", type=str, default="March2024", help="Starting month (e.g. January2024)")
    parser.add_argument("--end", type=str, default="March2024", help="Ending month (e.g. March2024)")
    args = parser.parse_args()

    print(f"Configuring HuggingFace cache: {hf_cache_dir}")
    os.makedirs(hf_cache_dir, exist_ok=True)

    # Check if we already have some data (simplistic check for existing cache directories)
    # The 'datasets' library naturally handles duplicate detection, but this informs the user.
    if os.listdir(hf_cache_dir):
        print("Detected existing datasets in cache. HuggingFace will skip redownloading existing files.")
    else:
        print("Cache is empty. Deep download starting...")

    print(f"\nTarget Configuration:")
    print(f" - Game Mode: {args.gamemode}")
    print(f" - Range:    {args.start} to {args.end}")
    print(f" - Quality:  1800+ Elo Only\n")

    print("Executing load_filtered_dataset...")
    
    # This automatically connects to HF, downloads to cache if missing, or reads from cache if present.
    dataset = load_filtered_dataset(
        min_month=args.start,
        max_month=args.end,
        elo_ranges=["1800+"],
        split="train",
        gamemode=args.gamemode
    )
    
    print(f"\nSuccess! Dataset Ready.")
    print(f" - Total Matches: {len(dataset)}")
    print(f" - Location:      {hf_cache_dir}")
    print("\nYou can now proceed to Step 2: EDA.")

if __name__ == "__main__":
    main()
