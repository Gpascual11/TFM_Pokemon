#!/bin/bash
# ──────────────────────────────────────────────
#  Start 6 Pokémon Showdown servers (ports 8000–8005)
#  Usage:  ./src/start_sim.sh
#  Stop:   Ctrl+C  (kills all 6 servers)
# ──────────────────────────────────────────────

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SHOWDOWN="$SCRIPT_DIR/pokemon-showdown/pokemon-showdown"
PORTS=(8000 8001 8002 8003 8004 8005)

# Kill any leftover servers
pkill -f "pokemon-showdown.*--port" 2>/dev/null || true
sleep 1

# Trap Ctrl+C to kill all background jobs
cleanup() {
    echo ""
    echo "🛑 Stopping all servers..."
    kill $(jobs -p) 2>/dev/null
    wait 2>/dev/null
    echo "✅ All servers stopped."
    exit 0
}
trap cleanup SIGINT SIGTERM

# Start servers
for port in "${PORTS[@]}"; do
    node "$SHOWDOWN" start --port "$port" --no-security &
    echo "🚀 Server launched on port $port (PID $!)"
done

# Wait for servers to become ready
echo ""
echo "⏳ Waiting for servers to start..."
sleep 3

ALL_OK=true
for port in "${PORTS[@]}"; do
    if bash -c "echo >/dev/tcp/127.0.0.1/$port" 2>/dev/null; then
        echo "   ✅ Port $port: ready"
    else
        echo "   ❌ Port $port: not ready yet"
        ALL_OK=false
    fi
done

if [ "$ALL_OK" = true ]; then
    echo ""
    echo "✅ All servers are running! You can now run simulations."
else
    echo ""
    echo "⚠️  Some servers may still be starting. Wait a few seconds and try again."
fi

echo ""
echo "Press Ctrl+C to stop all servers."
echo "──────────────────────────────────"

# Keep the script alive — wait for all background jobs
wait