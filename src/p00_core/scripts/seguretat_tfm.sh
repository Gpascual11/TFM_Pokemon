#!/bin/bash
# ==============================================================================
# Master Security & Health Monitor: seguretat_tfm.sh
# --------------------------------==============================================
# Purpose: Real-time hardware telemetry (CPU, RAM, NVMe) & interactive Telegram
#          bot polling handler for Pokemon Showdown TFM comparative benchmarks.
#
# Hardware Targets: AMD Ryzen 7 5700X3D (8C/16T, 96MB L3 Cache), 30GB DDR4 RAM, NVMe
#
# Features:
#   - Thermal & Memory Safety Thresholds (PageCache drop at 27.5GB, Panic at 29GB)
#   - Event-driven Telegram Bot Command Listener (Native 25s Long Polling)
#   - Automated 09:00 AM Daily Progress Summaries & Emergency Crash Recovery
# ==============================================================================

# ── 1. CREDENTIAL & ENVIRONMENT INITIALIZATION ────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"
ENV_FILE="$ROOT_DIR/.env"

if [ -f "$ROOT_DIR/.venv/bin/activate" ]; then
    # shellcheck source=/dev/null
    source "$ROOT_DIR/.venv/bin/activate"
fi

if [ -f "$ENV_FILE" ]; then
    # shellcheck source=/dev/null
    source "$ENV_FILE"
fi
TOKEN="${TELEGRAM_TOKEN:-}"
CHAT_ID="${TELEGRAM_CHAT_ID:-}"

# ── 2. SAFETY & HARDWARE THRESHOLD DEFINITIONS ─────────────────────────────────
# Thermal Limits (°C)
LIMIT_AVIS=85
LIMIT_PANIC=92

# RAM Usage & Thermal Limits
LIMIT_RAM_GB=29.0
LIMIT_RAM_TEMP_AVIS=70
LIMIT_RAM_TEMP_PANIC=80

# NVMe Storage Temperature Limits
LIMIT_NVME_TEMP_AVIS=70
LIMIT_NVME_TEMP_PANIC=80

LOG_FILE="$HOME/seguretat_tfm.log"

# ── 3. TELEGRAM & SYSTEM LOGGING UTILITIES ─────────────────────────────────────
send_telegram() {
    curl -s -X POST "https://api.telegram.org/bot$TOKEN/sendMessage" \
        -d chat_id="$CHAT_ID" \
        -d text="$1" > /dev/null
}

log_message() {
    local level="$1"
    local message="$2"
    local timestamp=$(date "+%Y-%m-%d %H:%M:%S")
    echo "[$timestamp] [$level] $message" | tee -a "$LOG_FILE"
}

# Ensure log file exists
touch "$LOG_FILE"

log_message "INFO" "Advanced security monitor (CPU, RAM, and NVMe) activated."
log_message "INFO" "Monitoring CPU (Temp/Status), RAM (Usage/Temp), and NVMe (Temp)..."
send_telegram "🚀 TFM Assistant Online for sirp! Monitoring Ryzen 7 5700X3D (16T), 30GB RAM & NVMe SSD..."

# Initial process state & time tracking
START_TIME_SEC=$(date +%s)
MIDNIGHT_GAMES=0
LAST_RECAP_DATE=""

OUT_DIR="$ROOT_DIR/data/benchmarks/all_10k/gen9randombattle"
START_COMPLETED_MATCHUPS=$(ls "$OUT_DIR"/*.csv 2>/dev/null | grep -v "_tmp_" | wc -l || echo 0)

tournament_was_running=true
if pgrep -f "benchmark.py" > /dev/null; then
    tournament_was_running=true
else
    tournament_was_running=false
fi

while true; do
    # 1. Read Tctl temperature of the CPU
    TEMP=$(sensors k10temp-pci-00c3 2>/dev/null | grep Tctl | awk '{print $2}' | tr -d '+°C' | cut -d. -f1)
    
    # Fallback to generic sensor if k10temp is unavailable
    if [ -z "$TEMP" ]; then
        TEMP=$(sensors 2>/dev/null | grep -E '(temp1|Core 0)' | head -n 1 | awk '{print $2}' | tr -d '+°C' | cut -d. -f1)
    fi

    # 2. Read RAM usage
    RAM_USED_MB=$(free -m | grep Mem | awk '{print $3}')
    RAM_TOTAL_MB=$(free -m | grep Mem | awk '{print $2}')
    RAM_USED_GB=$(echo "scale=2; $RAM_USED_MB / 1024" | bc)
    RAM_PCT=$(echo "scale=1; ($RAM_USED_MB / $RAM_TOTAL_MB) * 100" | bc)

    # 3. Read RAM temperatures (max jc42 sensor) and NVMe (Composite)
    RAM_TEMP=$(sensors 2>/dev/null | awk '/jc42/{flag=1; next} flag==1 && /temp1:/{print $2; flag=0}' | tr -d '+°C' | cut -d. -f1 | sort -nr | head -n 1)
    if [ -z "$RAM_TEMP" ]; then
        RAM_TEMP=0
    fi

    NVME_TEMP=$(sensors 2>/dev/null | awk '/nvme-/{flag=1; next} flag==1 && /Composite:/{print $2; flag=0}' | tr -d '+°C' | cut -d. -f1 | sort -nr | head -n 1)
    if [ -z "$NVME_TEMP" ]; then
        NVME_TEMP=0
    fi

    # 4. Check if tournament process is active
    TOURNAMENT_RUNNING=false
    if pgrep -f "benchmark.py" > /dev/null; then
        TOURNAMENT_RUNNING=true
    fi

    # Log current status every 5 minutes (approx 10 iterations of 30s)
    if [ $(( (SECONDS / 30) % 10 )) -eq 0 ]; then
        log_message "STATUS" "CPU: ${TEMP}°C | RAM: ${RAM_USED_GB}GB / $(echo "scale=2; $RAM_TOTAL_MB / 1024" | bc)GB (${RAM_PCT}%) | RAM Temp: ${RAM_TEMP}°C | NVMe Temp: ${NVME_TEMP}°C | Tournament: ${TOURNAMENT_RUNNING}"
    fi

    # --- CPU TEMPERATURE CONTROL ---
    # CASE 1.1: CRITICAL CPU EMERGENCY (Safety Shutdown)
    if [ -n "$TEMP" ] && [ "$TEMP" -ge "$LIMIT_PANIC" ]; then
        log_message "EMERGENCY" "CPU at $TEMP°C. Exceeds critical limit ($LIMIT_PANIC°C). SHUTTING DOWN PC."
        send_telegram "🚨 CRITICAL TFM: CPU reached $TEMP°C. SHUTTING DOWN PC FOR SAFETY."
        sleep 5
        poweroff || systemctl poweroff || sudo poweroff
        exit 1
    fi

    # CASE 1.2: CPU HIGH TEMP WARNING
    if [ -n "$TEMP" ] && [ "$TEMP" -ge "$LIMIT_AVIS" ]; then
        log_message "WARNING" "CPU at $TEMP°C. Exceeds warning limit ($LIMIT_AVIS°C)."
        send_telegram "⚠️ TFM ALERT: CPU is at $TEMP°C. Check airflow and active processes!"
        sleep 900 # Wait 15 minutes before re-alerting
    fi

    # --- RAM TEMPERATURE CONTROL ---
    # CASE 1.3: CRITICAL RAM TEMP EMERGENCY (Safety Shutdown)
    if [ "$RAM_TEMP" -ge "$LIMIT_RAM_TEMP_PANIC" ]; then
        log_message "EMERGENCY" "RAM at $RAM_TEMP°C. Exceeds critical limit ($LIMIT_RAM_TEMP_PANIC°C). SHUTTING DOWN PC."
        send_telegram "🚨 CRITICAL TFM: RAM reached $RAM_TEMP°C. SHUTTING DOWN PC FOR SAFETY."
        sleep 5
        poweroff || systemctl poweroff || sudo poweroff
        exit 1
    fi

    # CASE 1.4: RAM HIGH TEMP WARNING
    if [ "$RAM_TEMP" -ge "$LIMIT_RAM_TEMP_AVIS" ]; then
        log_message "WARNING" "RAM at $RAM_TEMP°C. Exceeds warning limit ($LIMIT_RAM_TEMP_AVIS°C)."
        send_telegram "⚠️ TFM ALERT: RAM is at $RAM_TEMP°C. Check case airflow!"
        sleep 900
    fi

    # --- NVMe TEMPERATURE CONTROL ---
    # CASE 1.5: CRITICAL NVMe TEMP EMERGENCY (Safety Shutdown)
    if [ "$NVME_TEMP" -ge "$LIMIT_NVME_TEMP_PANIC" ]; then
        log_message "EMERGENCY" "NVMe at $NVME_TEMP°C. Exceeds critical limit ($LIMIT_NVME_TEMP_PANIC°C). SHUTTING DOWN PC."
        send_telegram "🚨 CRITICAL TFM: NVMe SSD reached $NVME_TEMP°C. SHUTTING DOWN PC FOR SAFETY."
        sleep 5
        poweroff || systemctl poweroff || sudo poweroff
        exit 1
    fi

    # CASE 1.6: NVMe HIGH TEMP WARNING
    if [ "$NVME_TEMP" -ge "$LIMIT_NVME_TEMP_AVIS" ]; then
        log_message "WARNING" "NVMe at $NVME_TEMP°C. Exceeds warning limit ($LIMIT_NVME_TEMP_AVIS°C)."
        send_telegram "⚠️ TFM ALERT: NVMe SSD is at $NVME_TEMP°C. Check cooling and drive heatsink!"
        sleep 900
    fi

    # --- RAM USAGE CONTROL ---
    # CASE 2.1: MEMORY NEAR SATURATION (Auto-Cache Drop & Safe Recovery)
    if (( $(echo "$RAM_USED_GB >= 27.5" | bc -l) )); then
        log_message "WARNING" "RAM near saturation: ${RAM_USED_GB}GB used (${RAM_PCT}%). Flushing PageCache..."
        send_telegram "⚠️ MEMORY ALERT: RAM usage at ${RAM_USED_GB}GB (${RAM_PCT}%). Flushing PageCache memory."
        sync; sysctl -w vm.drop_caches=3 2>/dev/null || true
    fi

    if (( $(echo "$RAM_USED_GB >= $LIMIT_RAM_GB" | bc -l) )); then
        log_message "CRITICAL" "RAM at panic level (${RAM_USED_GB}GB / ${RAM_TOTAL_MB}MB). Resetting Showdown servers to reclaim memory..."
        send_telegram "🚨 CRITICAL MEMORY: RAM at ${RAM_USED_GB}GB (${RAM_PCT}%). Restarting Showdown services to reclaim RAM."
        pkill -f "pokemon-showdown" 2>/dev/null || true
        sleep 60
    fi

    # --- PROCESS MONITORING ---
    # CASE 3.1: Tournament Stopped (Finished or Crashed)
    if [ "$TOURNAMENT_RUNNING" = false ] && [ "$tournament_was_running" = true ]; then
        log_message "INFO" "Tournament process ('benchmark.py') has stopped."
        send_telegram "🔔 TFM NOTIFICATION: Tournament process ('benchmark.py') has stopped. Check if completed or crashed."
        tournament_was_running=false
    fi

    # Case 3.2: Tournament Restarted
    if [ "$TOURNAMENT_RUNNING" = true ] && [ "$tournament_was_running" = false ]; then
        log_message "INFO" "Tournament process ('benchmark.py') has restarted."
        tournament_was_running=true
    fi

    # --- TELEGRAM COMMAND LISTENER (/now - Native Long Polling) ---
    LAST_UPDATE_ID_FILE="$HOME/.telegram_last_update_id"
    LAST_UPDATE_ID=$(cat "$LAST_UPDATE_ID_FILE" 2>/dev/null || echo 0)

    # Long polling (timeout=25s): connection sleeps at 0% CPU on Telegram servers until /now is sent
    UPDATES=$(curl -s -m 30 "https://api.telegram.org/bot$TOKEN/getUpdates?offset=$LAST_UPDATE_ID&timeout=25")
    if [ -n "$UPDATES" ]; then
        # Parse last message text and update_id
        CMD_TEXT=$(echo "$UPDATES" | grep -o '"text":"[^"]*"' | tail -n 1 | cut -d'"' -f4 || true)
        NEW_OFFSET=$(echo "$UPDATES" | grep -o '"update_id":[0-9]*' | tail -n 1 | cut -d':' -f2 || true)

        if [ -n "$NEW_OFFSET" ] && [ "$NEW_OFFSET" -ge "$LAST_UPDATE_ID" ]; then
            NEXT_ID=$(( NEW_OFFSET + 1 ))
            echo "$NEXT_ID" > "$LAST_UPDATE_ID_FILE"
        fi

        # Normalize command text (strip @bot_username if present)
        CLEAN_CMD=$(echo "$CMD_TEXT" | sed -E 's/^\/([a-zA-Z0-9_]+)(@.*)?/\1/' | tr '[:upper:]' '[:lower:]')

        if [ "$CLEAN_CMD" = "now" ] || [ "$CLEAN_CMD" = "status" ]; then
            OUT_DIR="$ROOT_DIR/data/benchmarks/all_10k/gen9randombattle"
            ACTIVE_FILE=$(ls -t "$OUT_DIR"/_tmp_*.csv 2>/dev/null | head -n 1 || true)

            PROGRESS_MSG="No active matchup in progress."
            if [ -n "$ACTIVE_FILE" ]; then
                AGENT=$(awk -F',' 'NR==2 {print $3}' "$ACTIVE_FILE" 2>/dev/null || echo "")
                OPPONENT=$(awk -F',' 'NR==2 {print $4}' "$ACTIVE_FILE" 2>/dev/null || echo "")

                MATCHUP_TAG="${AGENT}_vs_${OPPONENT}"
                if [ -z "$AGENT" ] || [ -z "$OPPONENT" ]; then
                    MATCHUP_TAG=$(basename "$ACTIVE_FILE" | sed -E 's/_tmp_(.*)_p[0-9]+_b[0-9]+\.csv/\1/')
                fi

                MATCHUP_FILES=$(ls "$OUT_DIR"/_tmp_*${AGENT}_*${OPPONENT}*_p*.csv "$OUT_DIR"/_tmp_*${MATCHUP_TAG}*_p*.csv 2>/dev/null | sort -u || true)
                TOTAL_ROWS=0
                NUM_FILES=0
                if [ -n "$MATCHUP_FILES" ]; then
                    TOTAL_ROWS=$(wc -l $MATCHUP_FILES | tail -n 1 | awk '{print $1}')
                    NUM_FILES=$(echo "$MATCHUP_FILES" | wc -l)
                fi
                ACTUAL_ROWS=$(( TOTAL_ROWS - NUM_FILES ))
                [ $ACTUAL_ROWS -lt 0 ] && ACTUAL_ROWS=0

                EXIST_CSV="${OUT_DIR}/${MATCHUP_TAG}.csv"
                SAVED_GAMES=0
                if [ -f "$EXIST_CSV" ] && [ -s "$EXIST_CSV" ]; then
                    S_ROWS=$(wc -l < "$EXIST_CSV" 2>/dev/null || echo 0)
                    [ $S_ROWS -gt 1 ] && SAVED_GAMES=$(( S_ROWS - 1 ))
                fi
                TOTAL_DONE=$(( SAVED_GAMES + ACTUAL_ROWS ))

                TARGET_N=10000
                [[ "$MATCHUP_TAG" =~ (v18|v19|v20) ]] && TARGET_N=1000

                [ $TOTAL_DONE -gt $TARGET_N ] && TOTAL_DONE=$TARGET_N

                PCT=$(awk -v done="$TOTAL_DONE" -v target="$TARGET_N" 'BEGIN { printf "%.1f", (done/target)*100 }')
                PROGRESS_MSG="⚔️ *${MATCHUP_TAG}*: ${TOTAL_DONE}/${TARGET_N} (${PCT}%)"
            fi

            STATUS_REPLY="📊 *TFM Status*%0A${PROGRESS_MSG}%0A%0A🖥️ *System:*%0ACPU: ${TEMP}°C | RAM: ${RAM_USED_GB}GB (${RAM_PCT}%)%0ARAM Temp: ${RAM_TEMP}°C | NVMe: ${NVME_TEMP}°C"
            send_telegram "$STATUS_REPLY"
        fi

        if [ "$CLEAN_CMD" = "summary" ]; then
            OUT_DIR="$ROOT_DIR/data/benchmarks/all_10k/gen9randombattle"
            COMPLETED_COUNT=$(ls "$OUT_DIR"/*.csv 2>/dev/null | grep -v "_tmp_" | wc -l || echo 0)
            TOTAL_GAMES_DONE=0
            if [ "$COMPLETED_COUNT" -gt 0 ]; then
                TOTAL_GAMES_DONE=$(wc -l "$OUT_DIR"/*.csv 2>/dev/null | grep -v "_tmp_" | tail -n 1 | awk '{print $1}')
            fi

            SUMMARY_REPLY="🏆 *TFM TOURNAMENT SUMMARY*%0A-----------------------------------%0A✅ *Completed Matchups:* ${COMPLETED_COUNT}%0A🎮 *Total Games Recorded:* ~${TOTAL_GAMES_DONE}%0A📂 *Location:* data/benchmarks/all_10k"
            send_telegram "$SUMMARY_REPLY"
        fi

        if [ "$CLEAN_CMD" = "log" ]; then
            LOG_SNIPPET=$(tail -n 10 "$ROOT_DIR/paradigm_eval.log" 2>/dev/null || echo "No log file found.")
            # URL-encode newlines and send clean log lines
            ENCODED_LOG=$(echo "$LOG_SNIPPET" | sed 's/%/%25/g; s/ /%20/g' | awk '{printf "%s%%0A", $0}')
            send_telegram "📜 *LAST LOG OUTPUT:*%0A-----------------------------------%0A${ENCODED_LOG}"
        fi

        if [ "$CLEAN_CMD" = "pause" ]; then
            pkill -STOP -f "benchmark.py" 2>/dev/null || true
            pkill -STOP -f "worker.py" 2>/dev/null || true
            send_telegram "⏸️ BENCHMARK PAUSED: Execution stopped. Send /resume to continue."
        fi

        if [ "$CLEAN_CMD" = "resume" ]; then
            pkill -CONT -f "benchmark.py" 2>/dev/null || true
            pkill -CONT -f "worker.py" 2>/dev/null || true
            send_telegram "▶️ BENCHMARK RESUMED: Execution continued."
        fi

        if [ "$CLEAN_CMD" = "meme" ]; then
            MEME_JSON=$(curl -s "https://meme-api.com/gimme/pokemonmemes")
            MEME_URL=$(echo "$MEME_JSON" | grep -o '"url":"[^"]*"' | head -n 1 | cut -d'"' -f4 || true)
            MEME_TITLE=$(echo "$MEME_JSON" | grep -o '"title":"[^"]*"' | head -n 1 | cut -d'"' -f4 || echo "Pokemon Meme")

            if [ -n "$MEME_URL" ]; then
                curl -s -X POST "https://api.telegram.org/bot$TOKEN/sendPhoto" \
                    -d chat_id="$CHAT_ID" \
                    -d photo="$MEME_URL" \
                    -d caption="✨ *${MEME_TITLE}*" \
                    -d parse_mode="Markdown" > /dev/null || send_telegram "😂 Meme: ${MEME_URL}"
            else
                send_telegram "😅 Couldn't fetch a meme right now, try again!"
            fi
        fi

        if [ "$CLEAN_CMD" = "pokemon" ] || [ "$CLEAN_CMD" = "poke" ]; then
            POKE_ID=$(( (RANDOM % 898) + 1 ))
            POKE_JSON=$(curl -s "https://pokeapi.co/api/v2/pokemon/${POKE_ID}")
            POKE_NAME=$(echo "$POKE_JSON" | grep -o '"name":"[^"]*"' | head -n 1 | cut -d'"' -f4 | tr '[:lower:]' '[:upper:]' || echo "POKEMON")
            SPRITE_URL="https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/${POKE_ID}.png"

            QUOTES=(
                "I see now that the circumstances of one's birth are irrelevant. It is what you do with the gift of life that determines who you are. — Mewtwo"
                "There’s no sense in going out of your way to get somebody to like you. Just be yourself. — Ash Ketchum"
                "Strong Pokémon. Weak Pokémon. That is only the selfish perception of people. Truly skilled trainers should try to win with their favorites. — Karen"
                "It’s more important to master the cards you’re holding than to complain about the ones your opponent was dealt. — Grimsley"
                "A wildfire burns bright, but it leaves nothing behind. A champion learns to endure. — Cynthia"
                "You said you have a dream... That dream... Make it come true! — N"
                "Even if we don't understand each other, that's not a reason to reject each other. There are two sides to any argument. — Alder"
                "You can't expect to meet a legendary Pokémon without putting in legendary effort! — Steven Stone"
                "Smell ya later! — Blue"
                "No matter how dark the night, morning always comes. — Lucario"
                "It’s not whether you win or lose, it’s how much you learn from every battle. — Brock"
                "The world is full of different people, Pokémon, and ways of thinking. — Professor Oak"
                "A battle isn't over until the final faint! — Lance"
                "Failing doesn't make you a failure. Giving up does. — Professor Kukui"
                "My heart beats for Pokémon battles! — Red"
            )
            RANDOM_QUOTE=${QUOTES[$(( RANDOM % ${#QUOTES[@]} ))]}

            curl -s -X POST "https://api.telegram.org/bot$TOKEN/sendPhoto" \
                -d chat_id="$CHAT_ID" \
                -d photo="$SPRITE_URL" \
                -d caption="🌟 *#${POKE_ID} - ${POKE_NAME}*%0A%0A💬 *\"${RANDOM_QUOTE}\"*" \
                -d parse_mode="Markdown" > /dev/null || send_telegram "🌟 #${POKE_ID} ${POKE_NAME}: ${RANDOM_QUOTE}"
        fi

        if [ "$CLEAN_CMD" = "session" ] || [ "$CLEAN_CMD" = "runtime" ]; then
            NOW_SEC=$(date +%s)
            ELAPSED_HOURS=$(awk -v start="$START_TIME_SEC" -v now="$NOW_SEC" 'BEGIN { printf "%.1f", (now-start)/3600 }')
            OUT_DIR="$ROOT_DIR/data/benchmarks/all_10k/gen9randombattle"
            CURRENT_COMPLETED=$(ls "$OUT_DIR"/*.csv 2>/dev/null | grep -v "_tmp_" | wc -l || echo 0)
            MATCHUPS_MADE=$(( CURRENT_COMPLETED - START_COMPLETED_MATCHUPS ))
            [ $MATCHUPS_MADE -lt 0 ] && MATCHUPS_MADE=0

            TOTAL_ROWS=$(wc -l "$OUT_DIR"/*.csv 2>/dev/null | grep -v "_tmp_" | tail -n 1 | awk '{print $1}' || echo 0)
            EXACT_GAMES_SESSION=$(( TOTAL_ROWS > CURRENT_COMPLETED ? TOTAL_ROWS - CURRENT_COMPLETED : 0 ))

            send_telegram "⚡ *TFM SESSION REPORT*%0A-----------------------------------%0A👤 *Host:* sirp @ Ryzen 7 5700X3D%0A⏱️ *Session Runtime:* ${ELAPSED_HOURS} hours%0A✅ *Matchups Finished:* ${MATCHUPS_MADE}%0A🎮 *Games Completed:* ${EXACT_GAMES_SESSION}%0A%0A🖥️ *Live Stats:*%0ACPU: ${TEMP}°C | RAM: ${RAM_USED_GB}GB"
        fi
    fi

    # --- AUTOMATED 9:00 AM RECAP ALERT ---
    CURRENT_HOUR=$(date +%H)
    CURRENT_MIN=$(date +%M)
    TODAY_STR=$(date +%Y-%m-%d)

    # Capture midnight (00:00) baseline
    if [ "$CURRENT_HOUR" = "00" ] && [ "$CURRENT_MIN" -lt 05 ]; then
        OUT_DIR="$ROOT_DIR/data/benchmarks/all_10k/gen9randombattle"
        MIDNIGHT_MATCHUPS=$(ls "$OUT_DIR"/*.csv 2>/dev/null | grep -v "_tmp_" | wc -l || echo 0)
        MIDNIGHT_ROWS=$(wc -l "$OUT_DIR"/*.csv 2>/dev/null | grep -v "_tmp_" | tail -n 1 | awk '{print $1}' || echo 0)
        MIDNIGHT_GAMES=$(( MIDNIGHT_ROWS > MIDNIGHT_MATCHUPS ? MIDNIGHT_ROWS - MIDNIGHT_MATCHUPS : 0 ))
    fi

    # Send 09:00 AM Recap automatically
    if [ "$CURRENT_HOUR" = "09" ] && [ "$LAST_RECAP_DATE" != "$TODAY_STR" ]; then
        LAST_RECAP_DATE="$TODAY_STR"
        OUT_DIR="$ROOT_DIR/data/benchmarks/all_10k/gen9randombattle"
        NOW_MATCHUPS=$(ls "$OUT_DIR"/*.csv 2>/dev/null | grep -v "_tmp_" | wc -l || echo 0)
        NOW_ROWS=$(wc -l "$OUT_DIR"/*.csv 2>/dev/null | grep -v "_tmp_" | tail -n 1 | awk '{print $1}' || echo 0)
        NOW_GAMES=$(( NOW_ROWS > NOW_MATCHUPS ? NOW_ROWS - NOW_MATCHUPS : 0 ))

        NIGHT_MATCHUPS=$(( NOW_MATCHUPS - MIDNIGHT_MATCHUPS ))
        [ $NIGHT_MATCHUPS -lt 0 ] && NIGHT_MATCHUPS=$NOW_MATCHUPS
        NIGHT_GAMES=$(( NOW_GAMES - MIDNIGHT_GAMES ))
        [ $NIGHT_GAMES -lt 0 ] && NIGHT_GAMES=$NOW_GAMES

        send_telegram "☀️ *GOOD MORNING! 9:00 AM RECAP*%0A-----------------------------------%0A🌙 *Overnight Matchups (00:00 - 09:00):* ${NIGHT_MATCHUPS}%0A🎮 *Overnight Games Completed:* ${NIGHT_GAMES}%0A%0A🖥️ *System Status:*%0ACPU Temp: ${TEMP}°C | RAM Usage: ${RAM_USED_GB}GB%0ANVMe Temp: ${NVME_TEMP}°C | Status: Running Smoothly!"
    fi
done
