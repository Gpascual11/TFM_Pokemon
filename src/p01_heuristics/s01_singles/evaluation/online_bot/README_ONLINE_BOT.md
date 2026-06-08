# Pokémon Showdown Online Bot Runner

This utility allows you to run any heuristic agent (like `v13`) on the official Smogon Pokémon Showdown server to test its capabilities against real human players or directly challenge it yourself.

---

## 1. Installation & Environment Setup

Make sure you have your dependencies activated using `uv`:
```bash
# Verify the script is executable
chmod +x src/p01_heuristics/s01_singles/evaluation/online_bot/run_online_bot.py
```

---

## 2. Modes of Operation

### Mode A: Challenge Mode (`accept`) - RECOMMENDED FOR TESTING
In this mode, the bot sits online and waits for challenges. It does not play public ladder games automatically. This is the safest way to test without triggering bot protection.

1. Start the bot:
   ```bash
   uv run python src/p01_heuristics/s01_singles/evaluation/online_bot/run_online_bot.py --username "YourBotUsername" --password "YourBotPassword" --mode accept
   ```
2. Log into your personal account on [play.pokemonshowdown.com](https://play.pokemonshowdown.com).
3. Search for your bot's username and click **"Challenge"**. Select `Gen 9 Random Battle` (or whatever format you started the bot with).
4. The bot will automatically accept and play. You can watch it make decisions in real-time.

---

### Mode B: Ladder Mode (`ladder`)
In this mode, the bot connects to the server and registers with the matchmaking system to fight real human players on the public ladder.

* **Play a batch of 20 games**:
  ```bash
  uv run python src/p01_heuristics/s01_singles/evaluation/online_bot/run_online_bot.py --username "YourBotUsername" --password "YourBotPassword" --mode ladder --games 20 --agent v13
  ```

---

## 3. Best Practices & Safety (Should I run it all day?)

* **Do NOT run the bot all day**: 
  * Running an unregistered bot playing hundreds of games 24/7 will likely trigger Pokémon Showdown's security and get your IP or bot account **banned**.
  * Showdown admins require a specific "Bot" rank tag for accounts running persistent matchmaking games.
* **Run in short, controlled batches**:
  * Running the bot for **30–60 minutes** (e.g., `--games 30`) is more than enough to play 30 games and establish an Elo rating.
  * Bots move instantly, so battles finish extremely quickly. You will gather a statistically significant sample size in a short session.
* **Keep a Log**:
  * You can record the ladder Elo of the bot at the start and end of your run to document in your thesis.
