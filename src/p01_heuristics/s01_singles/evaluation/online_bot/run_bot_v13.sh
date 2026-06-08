#!/usr/bin/env bash
# Pokémon Showdown Bot quick launcher script for HeuristicV13

# Default credentials and configuration
USERNAME="SirPThesis"
PASSWORD="***REDACTED***"
MODE="accept"
AGENT="v13"
FORMAT="gen9randombattle"
GAMES=20

# Allow simple parameter overrides from command line
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --username) USERNAME="$2"; shift ;;
        --mode) MODE="$2"; shift ;;
        --agent) AGENT="$2"; shift ;;
        --format) FORMAT="$2"; shift ;;
        --games) GAMES="$2"; shift ;;
        *) echo "Unknown parameter passed: $1"; exit 1 ;;
    esac
    shift
done

# Navigate to the workspace root directory
SCRIPTPATH="$( cd -- "$(dirname "$0")" >/dev/null 2>&1 ; pwd -P )"
cd "$SCRIPTPATH/../../../../.."

echo "🤖 Starting Pokémon Showdown Bot (Upgraded V13)..."
echo "👤 Username: $USERNAME"
echo "🎮 Mode:     $MODE"
echo "🧠 Agent:    $AGENT"
if [ "$MODE" = "ladder" ]; then
    echo "⚔️  Format:   $FORMAT"
    echo "📊 Games:    $GAMES"
    uv run python src/p01_heuristics/s01_singles/evaluation/online_bot/run_online_bot.py \
        --username "$USERNAME" \
        --password "$PASSWORD" \
        --mode "$MODE" \
        --agent "$AGENT" \
        --format "$FORMAT" \
        --games "$GAMES"
else
    uv run python src/p01_heuristics/s01_singles/evaluation/online_bot/run_online_bot.py \
        --username "$USERNAME" \
        --password "$PASSWORD" \
        --mode "$MODE" \
        --agent "$AGENT"
fi
