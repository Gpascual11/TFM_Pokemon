#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
#  Launch multiple Pokémon Showdown servers dynamically
#  Usage:  ./src/p03_scripts/p03_launch_custom_servers.sh <count>
#  Example:  ./src/p03_scripts/p03_launch_custom_servers.sh 4
# ─────────────────────────────────────────────────────────────────────────────

set -e

# Configuration
COUNT=${1:-1}
BASE_PORT=8000
ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
SHOWDOWN="$ROOT_DIR/pokemon-showdown/pokemon-showdown"

# Validate input
if ! [[ "$COUNT" =~ ^[0-9]+$ ]] || [ "$COUNT" -lt 1 ] || [ "$COUNT" -gt 10 ]; then
    echo "❌ Error: Please provide a number of servers between 1 and 10."
    echo "Usage: $0 <1-10>"
    exit 1
fi

# Kill any leftover servers
echo "🧹 Cleaning up old server processes..."
pkill -f "pokemon-showdown.*--port" 2>/dev/null || true
sleep 1

# Trap Ctrl+C to kill all background jobs
cleanup() {
    echo ""
    echo "🛑 Stopping all $COUNT servers..."
    kill $(jobs -p) 2>/dev/null
    wait 2>/dev/null
    echo "✅ All servers stopped."
    exit 0
}
trap cleanup SIGINT SIGTERM

echo "🚀 Launching $COUNT Pokémon Showdown servers..."
echo "──────────────────────────────────────────────"

# Start servers
for ((i=0; i<COUNT; i++)); do
    PORT=$((BASE_PORT + i))
    node "$SHOWDOWN" start --port "$PORT" --no-security &
    echo "   ✅ [Port $PORT] Server launched (PID $!)"
    # Wait a bit between launches to avoid race conditions on shared config files
    sleep 2
done

echo "──────────────────────────────────────────────"
echo "⏳ Waiting 3 seconds for availability..."
sleep 3

# Final check
for ((i=0; i<COUNT; i++)); do
    PORT=$((BASE_PORT + i))
    if bash -c "echo >/dev/tcp/127.0.0.1/$PORT" 2>/dev/null; then
        echo "   📡 Port $PORT: READY"
    else
        echo "   ⚠️  Port $PORT: Not responding yet"
    fi
done

echo ""
echo "🔥 Done! All $COUNT servers are running."
echo "Press Ctrl+C to stop all of them."
wait
