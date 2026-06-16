#!/bin/bash
# run_v10_diagnostic.sh — V10 validation & benchmark
# Phase 1: 100 games (quick check for crashes)
# Phase 2: 1000 games (statistical significance) — change N_BATTLES below

eval "$(grep -A3 '^avis_telegram()' ~/.bashrc)"

GENS="gen1randombattle gen5randombattle gen9randombattle"
AGENTS="v10"
N_BATTLES=100
PORTS=8
CONCURRENCY=20
OUT_BASE="data/testing/backup/benchmarks_v10"
MAX_RETRIES=2

cleanup() {
    pkill -f "pokemon-showdown" 2>/dev/null
    pkill -f "worker.py" 2>/dev/null
    for PORT in $(seq 8000 $((8000 + PORTS - 1))); do
        fuser -k "$PORT/tcp" 2>/dev/null
    done
    pkill -f "p00_core/engine" 2>/dev/null
    sleep 3
}

trap 'cleanup; avis_telegram "KILLED: V10 diagnostic was terminated"; exit 1' SIGTERM SIGINT SIGHUP

avis_telegram "Starting V10 diagnostic: $N_BATTLES games x 3 gens ($(date '+%H:%M'))"

cleanup

for GEN in $GENS; do
    avis_telegram "[$GEN] V10 starting"
    START_GEN=$(date +%s)

    for AGENT in $AGENTS; do
        ATTEMPT=0
        SUCCESS=false

        while [ $ATTEMPT -lt $MAX_RETRIES ] && [ "$SUCCESS" = false ]; do
            ATTEMPT=$((ATTEMPT + 1))

            if [ $ATTEMPT -gt 1 ]; then
                avis_telegram "[$GEN] $AGENT retry $ATTEMPT/$MAX_RETRIES"
                cleanup
                sleep 5
            fi

            START_AGENT=$(date +%s)

            uv run python src/p00_core/engine/benchmark.py $N_BATTLES \
                --agents "$AGENT" \
                --ports $PORTS \
                --concurrency $CONCURRENCY \
                --battle-format "$GEN" \
                --out "$OUT_BASE/$GEN" \
                --restart-every 3
            EXIT_CODE=$?

            END_AGENT=$(date +%s)
            AGENT_DURATION=$(( END_AGENT - START_AGENT ))
            AGENT_MIN=$(( AGENT_DURATION / 60 ))

            if [ $EXIT_CODE -eq 0 ]; then
                SUCCESS=true
                avis_telegram "[$GEN] $AGENT done (${AGENT_MIN}m)"
            else
                avis_telegram "[$GEN] $AGENT FAIL attempt $ATTEMPT (exit $EXIT_CODE)"
                cleanup
            fi
        done

        if [ "$SUCCESS" = false ]; then
            avis_telegram "[$GEN] $AGENT ABORT after $MAX_RETRIES attempts"
        fi
    done

    END_GEN=$(date +%s)
    GEN_DURATION=$(( END_GEN - START_GEN ))
    GEN_MIN=$(( GEN_DURATION / 60 ))

    avis_telegram "[$GEN] V10 done (${GEN_MIN}m)"
    cleanup
done

avis_telegram "V10 diagnostic DONE ($N_BATTLES games). Results in $OUT_BASE/ ($(date '+%H:%M'))"
