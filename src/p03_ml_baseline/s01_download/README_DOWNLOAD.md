# Step 1: Dataset Acquisition

## Overview
This folder correctly isolates the first step of our Machine Learning pipeline: downloading the raw human replay data to be analyzed.

In imitation learning (Behavioral Cloning), the model is entirely dependent on the quality of the experts it observes. 

## How We Get The Data
Instead of randomly scraping the internet manually, our project connects to the HuggingFace `datasets` library via the vendored `pokechamp` utilities.

When you run `download_dataset.py`, it executes `load_filtered_dataset()`. Behind the scenes, this:
1. Connects to the HuggingFace Hub.
2. Downloads the massive `milkkarten/pokechamp` dataset.
3. Automatically routes the download to the 1TB external drive cache (`data/huggingface_cache`) to prevent completely filling your local root disk.
4. Filters the dataset down realistically to only Gen 9 OU (OverUsed) singles format, played in March 2024, by players with an Elo rating of **1800 or higher**.

## Why This Matters
By extracting games from strictly 1800+ Elo players immediately, we guarantee that the EDA (Step 2) and the XGBoost model (Step 3) are studying "expert" decision-making, rather than random or mathematically suboptimal moves from beginners.
