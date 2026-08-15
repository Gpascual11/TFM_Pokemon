#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
#  Launch multiple Pokémon Showdown servers dynamically
#  Usage:  ./src/p00_core/scripts/launch_custom_servers.sh <count> [base_port]
#  Example:  ./src/p00_core/scripts/launch_custom_servers.sh 4
#
#  Does NOT pkill other pokemon-showdown jobs. Ports that already accept TCP
#  are reused so a second PPO/eval process cannot kill a running heuristic
#  benchmark (and vice versa). Heuristic `benchmark.py` still pkill's itself
#  before calling this script, so a deliberate restart still works.
# ─────────────────────────────────────────────────────────────────────────────

set -e

# Configuration
COUNT=${1:-1}
BASE_PORT=${2:-8000}
ROOT_DIR="$(cd "$(dirname "$0")/../../.." && pwd)"
SHOWDOWN="$ROOT_DIR/pokemon-showdown/pokemon-showdown"

# Validate input
if ! [[ "$COUNT" =~ ^[0-9]+$ ]] || [ "$COUNT" -lt 1 ] || [ "$COUNT" -gt 10 ]; then
    echo "❌ Error: Please provide a number of servers between 1 and 10."
    echo "Usage: $0 <1-10> [base_port]"
    exit 1
fi

port_listening() {
    bash -c "echo >/dev/tcp/127.0.0.1/$1" 2>/dev/null
}

# Trap Ctrl+C to kill only servers this invocation started
cleanup() {
    echo ""
    echo "🛑 Stopping servers started by this launcher..."
    if [ -n "${STARTED_PIDS:-}" ]; then
        kill $STARTED_PIDS 2>/dev/null || true
        wait 2>/dev/null || true
    fi
    echo "✅ Launcher servers stopped (reused ports left running)."
    exit 0
}
trap cleanup SIGINT SIGTERM

echo "🚀 Launching $COUNT Pokémon Showdown servers from port $BASE_PORT..."
echo "──────────────────────────────────────────────"

STARTED_PIDS=""
STARTED_COUNT=0

for ((i=0; i<COUNT; i++)); do
    PORT=$((BASE_PORT + i))
    if port_listening "$PORT"; then
        echo "   ♻️  [Port $PORT] already listening — reusing (not killed)"
        continue
    fi
    node "$SHOWDOWN" start --port "$PORT" --no-security &
    PID=$!
    STARTED_PIDS="$STARTED_PIDS $PID"
    STARTED_COUNT=$((STARTED_COUNT + 1))
    echo "   ✅ [Port $PORT] Server launched (PID $PID)"
    # Wait a bit between launches to avoid race conditions on shared config files
    sleep 2
done

echo "──────────────────────────────────────────────"
if [ "$STARTED_COUNT" -eq 0 ]; then
    echo "♻️  All $COUNT requested ports were already up. Nothing started."
else
    echo "⏳ Waiting 3 seconds for availability..."
    sleep 3
fi

# Final check
for ((i=0; i<COUNT; i++)); do
    PORT=$((BASE_PORT + i))
    if port_listening "$PORT"; then
        echo "   📡 Port $PORT: READY"
    else
        echo "   ⚠️  Port $PORT: Not responding yet"
    fi
done

echo ""
echo "🔥 Done! $COUNT ports requested, $STARTED_COUNT started this invocation."

if [ "${TFM_SHOWDOWN_NO_WAIT:-0}" = "1" ]; then
    echo "TFM_SHOWDOWN_NO_WAIT=1 — exiting without waiting (node processes keep running)."
    exit 0
fi

if [ "$STARTED_COUNT" -eq 0 ]; then
    exit 0
fi

echo "Press Ctrl+C to stop servers started by this launcher (reused ports stay up)."
wait
