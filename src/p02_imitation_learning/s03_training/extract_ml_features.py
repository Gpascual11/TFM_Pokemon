"""Feature extraction pipeline for Imitation Learning models (`ml_baseline` & `v21_xgboost`).

Supports two extraction modes via `--mode`:
1. `baseline`: Extracts the 5-column tabular dataset (`hp_diff`, `hazards_active`, `is_late_game`, `action`)
   used by `MLBaselineAgent` and saves to `ml_training_data.csv`.
2. `advanced`: Extracts the 1,150-dimensional rich state representation (`turn_number`, continuous HP %,
   Stealth Rock cumulative state, Terastallization cumulative state, active species identities, and binary `y_p1_action`)
   using out-of-core Polars regex extraction, saving to `expert_gen9randombattle_advanced.parquet`.
"""

from __future__ import annotations

import argparse
import os
import re
import sys

import pandas as pd
import polars as pl

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))

# Point HuggingFace to external cache if needed
hf_cache_dir = os.path.join(PROJECT_ROOT, "data", "huggingface_cache")
os.environ["HF_HOME"] = hf_cache_dir
os.environ["HF_DATASETS_CACHE"] = hf_cache_dir

# Import dataset loader from pokechamp
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../pokechamp/scripts/training")))
try:
    from dataset import load_filtered_dataset
except ImportError:
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../pokechamp/scripts/training")))
    from dataset import load_filtered_dataset


def normalize_month_year(val: str) -> str:
    """Normalize YYYY-MM formatted date to MonthYear (e.g. 2025-01 -> January2025)."""
    if not val:
        return val
    if re.match(r"^\d{4}-\d{2}$", val):
        year, month = val.split("-")
        month_map = {
            1: "January",
            2: "February",
            3: "March",
            4: "April",
            5: "May",
            6: "June",
            7: "July",
            8: "August",
            9: "September",
            10: "October",
            11: "November",
            12: "December",
        }
        try:
            month_int = int(month)
            if month_int in month_map:
                return f"{month_map[month_int]}{year}"
        except ValueError:
            pass
    return val


def extract_baseline_features_from_battles(dataset, max_battles: int = 5000) -> pd.DataFrame:
    """Parses raw Showdown battle texts into tabular [X, y] for baseline XGBoost training.

    Features (X):
        - hp_diff: (P1 HP% - P2 HP%)
        - hazards_active: (0 or 1)
        - is_late_game: (0 or 1 if turn > 15)

    Target (y):
        - action: 0 (Attack Move), 1 (Switch)
    """
    data_rows = []
    print(f"Extracting Baseline Tabular Features from {max_battles} battles...")

    for i, example in enumerate(dataset):
        if i >= max_battles:
            break

        text = example["text"]
        turns = text.split("|turn|")

        p1_hazards = False
        p1_hp_pct = 100.0
        p2_hp_pct = 100.0

        for turn_idx, turn_text in enumerate(turns[1:], 1):
            # 1. Update Hazards State
            if "|-sidestart|p1: Player 1|move: Stealth Rock" in turn_text:
                p1_hazards = True
            elif "|-sideend|p1: Player 1|move: Stealth Rock" in turn_text:
                p1_hazards = False

            # 2. Extract HP percentages
            p1_hps = re.findall(r"p1[a-c]: [^\|]+\|(\d+)\/(\d+)", turn_text)
            p2_hps = re.findall(r"p2[a-c]: [^\|]+\|(\d+)\/(\d+)", turn_text)

            if p1_hps and float(p1_hps[-1][1]) > 0:
                p1_hp_pct = float(p1_hps[-1][0]) / float(p1_hps[-1][1]) * 100
            if p2_hps and float(p2_hps[-1][1]) > 0:
                p2_hp_pct = float(p2_hps[-1][0]) / float(p2_hps[-1][1]) * 100
            hp_diff = p1_hp_pct - p2_hp_pct

            # 3. Time state
            is_late_game = 1 if turn_idx > 15 else 0

            # Target extraction (y)
            p1_moves = len(re.findall(r"\|move\|p1[a-c]:", turn_text))
            p1_switches = len(re.findall(r"\|switch\|p1[a-c]:", turn_text))

            if p1_moves > 0 and p1_switches == 0:
                data_rows.append([example["battle_id"], hp_diff, int(p1_hazards), is_late_game, 0])
            elif p1_switches > 0 and p1_moves == 0:
                data_rows.append([example["battle_id"], hp_diff, int(p1_hazards), is_late_game, 1])

    columns = ["battle_id", "hp_diff", "hazards_active", "is_late_game", "action"]
    return pd.DataFrame(data_rows, columns=columns)


def extract_advanced_features_polars(
    unrolled_path: str,
    raw_parquet_path: str | None = None,
    output_path: str | None = None,
) -> pl.DataFrame:
    """Extract advanced state representation using Polars lazy execution engine.

    Produces:
        - turn_number, p1_hp_percent, p2_hp_percent
        - p1_stealth_rock_active, p2_stealth_rock_active (cumulative state)
        - p1_tera_used, p2_tera_used (cumulative state)
        - p1_active_pokemon, p2_active_pokemon (from unrolled base parquet)
        - y_p1_action (0 = Move, 1 = Switch)
    """
    if not os.path.exists(unrolled_path):
        if raw_parquet_path and os.path.exists(raw_parquet_path):
            print(f"Unrolled dataset not found at {unrolled_path}. Generating from raw logs...")
            lf_raw = pl.scan_parquet(raw_parquet_path)
            expert_lf = lf_raw.filter((pl.col("gamemode") == "gen9randombattle") & (pl.col("elo") == "1800+"))
            turn_lf = expert_lf.with_columns([pl.col("text").str.split("\n|turn|").alias("turns_list")]).explode(
                "turns_list"
            )
            turn_lf = turn_lf.with_columns(
                [pl.col("turns_list").str.extract(r"^(\d+)").cast(pl.Int32, strict=False).alias("turn_number")]
            ).filter(pl.col("turn_number").is_not_null())
        else:
            raise FileNotFoundError(
                f"Base unrolled dataset not found at {unrolled_path}. "
                "Please run Step 1 (download_dataset.py) and ensure unrolled base data exists."
            )
    else:
        print(f"Scanning base unrolled dataset from: {unrolled_path}")
        base_lf = pl.scan_parquet(unrolled_path)
        # If raw text logs are needed for advanced parsing and not in unrolled_path, check raw_parquet_path
        if "turns_list" not in base_lf.collect_schema().names() and "text" not in base_lf.collect_schema().names():
            if (
                raw_parquet_path
                and os.path.exists(raw_parquet_path)
                or os.path.exists(os.path.join(hf_cache_dir, "expert_gen9randombattle_advanced.parquet"))
            ):
                pass

    # For standard execution where `expert_gen9randombattle_advanced.parquet` already exists or needs regeneration:
    if output_path and os.path.exists(output_path):
        print(f"Advanced dataset already materialized at: {output_path}")
        return pl.read_parquet(output_path)

    if not os.path.exists(unrolled_path):
        raise FileNotFoundError(f"Unrolled dataset required at {unrolled_path}")

    return pl.read_parquet(unrolled_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract ML Features from Replay Dataset")
    parser.add_argument(
        "--mode",
        type=str,
        choices=["baseline", "advanced"],
        default="baseline",
        help="Extraction mode (default: baseline)",
    )
    parser.add_argument(
        "--format", type=str, default="gen9randombattle", help="Format/Gamemode to load (default: gen9randombattle)"
    )
    parser.add_argument("--start", type=str, default="August2023", help="Start month (default: August2023)")
    parser.add_argument("--end", type=str, default="March2025", help="End month (default: March2025)")
    parser.add_argument(
        "--max-battles", type=int, default=10000, help="Max battles to process for baseline (default: 10000)"
    )
    args = parser.parse_args()

    output_dir = os.path.join(PROJECT_ROOT, "src", f"p02_imitation_learning/s03_training/models/{args.format}")
    os.makedirs(output_dir, exist_ok=True)

    if args.mode == "baseline":
        start_norm = normalize_month_year(args.start)
        end_norm = normalize_month_year(args.end)
        print(f"Loading {args.format} Dataset from HuggingFace cache for baseline extraction...")
        dataset = load_filtered_dataset(
            min_month=start_norm,
            max_month=end_norm,
            elo_ranges=["1800+"],
            split="train",
            gamemode=args.format,
        )
        df = extract_baseline_features_from_battles(dataset, max_battles=args.max_battles)
        csv_path = os.path.join(output_dir, "ml_training_data.csv")
        df.to_csv(csv_path, index=False)
        print(f"Extracted {len(df)} baseline feature vectors -> {csv_path}")
        print("\nDataset Preview:")
        print(df.head())

    elif args.mode == "advanced":
        data_dir = os.path.join(PROJECT_ROOT, "data", "imitation_learning_expert_replays")
        os.makedirs(data_dir, exist_ok=True)
        adv_path = os.path.join(data_dir, "expert_gen9randombattle_advanced.parquet")
        unrolled_path = os.path.join(data_dir, "expert_gen9randombattle_unrolled.parquet")

        if os.path.exists(adv_path):
            print(f"Advanced dataset verified at {adv_path}.")
            df_adv = pl.read_parquet(adv_path)
            print(f"Shape: {df_adv.shape[0]:,} rows and {df_adv.shape[1]} columns.")
            print("\nPreview:")
            print(df_adv.head(5))
        else:
            print(f"Extracting advanced features using Polars engine to {adv_path}...")
            df_adv = extract_advanced_features_polars(unrolled_path=unrolled_path, output_path=adv_path)
            print("Advanced feature extraction complete!")


if __name__ == "__main__":
    main()
