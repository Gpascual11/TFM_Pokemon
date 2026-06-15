import os
import sys
import argparse
import re

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
    parser = argparse.ArgumentParser(description="Download Pokemon Replay Dataset with Smart Caching")
    parser.add_argument("--gamemode", type=str, default="gen9randombattle", help="Game mode (e.g. gen9randombattle, gen9ou)")
    parser.add_argument("--start", type=str, default="January2025", help="Starting month (e.g. 2025-01 or January2025)")
    parser.add_argument("--end", type=str, default="April2026", help="Ending month (e.g. 2026-04 or April2026)")
    args = parser.parse_args()

    # Normalize dates if in YYYY-MM format
    start_normalized = normalize_month_year(args.start)
    end_normalized = normalize_month_year(args.end)

    print(f"Configuring HuggingFace cache: {hf_cache_dir}")
    os.makedirs(hf_cache_dir, exist_ok=True)

    if os.listdir(hf_cache_dir):
        print("Detected existing datasets in cache. HuggingFace will skip redownloading existing files.")
    else:
        print("Cache is empty. Deep download starting...")

    print(f"\nTarget Configuration:")
    print(f" - Game Mode: {args.gamemode}")
    print(f" - Range:    {start_normalized} to {end_normalized} (Input: {args.start} to {args.end})")
    print(f" - Quality:  1800+ Elo Only\n")

    print("Executing load_filtered_dataset...")
    
    # This automatically connects to HF, downloads to cache if missing, or reads from cache if present.
    dataset = load_filtered_dataset(
        min_month=start_normalized,
        max_month=end_normalized,
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
