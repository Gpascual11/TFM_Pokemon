#!/bin/bash
# run_v12_10000.sh — 10000 games per matchup for V12 against major opponents
# Statistical validation: ±0.98% CI at 95% confidence

if grep -q 'avis_telegram()' ~/.bashrc; then
    eval "$(grep -A3 '^avis_telegram()' ~/.bashrc)"
else
    avis_telegram() { echo "$1"; }
fi

GENS="gen1randombattle gen5randombattle gen9randombattle"
AGENT="v12"
OPPONENTS="v7 v8 v9 v10 v11 abyssal simple_heuristic random"
N_BATTLES=10000
PORTS=8
CONCURRENCY=20
OUT_BASE="data/testing/backup/benchmarks_v12_10k"
MAX_RETRIES=3

cleanup() {
    pkill -f "pokemon-showdown" 2>/dev/null
    pkill -f "worker.py" 2>/dev/null
    for PORT in $(seq 8000 $((8000 + PORTS - 1))); do
        fuser -k "$PORT/tcp" 2>/dev/null
    done
    pkill -f "p00_core/engine" 2>/dev/null
    sleep 3
}

trap 'cleanup; avis_telegram "KILLED: V12 10k benchmark was terminated"; exit 1' SIGTERM SIGINT SIGHUP

TOTAL_START=$(date +%s)
avis_telegram "Starting V12 10k benchmark: $N_BATTLES games x ${GENS// /, } x $AGENT vs ${OPPONENTS// /, } ($(date '+%H:%M'))"

cleanup

for GEN in $GENS; do
    avis_telegram "[$GEN] Starting V12 10k matchups"
    START_GEN=$(date +%s)

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
            --opponents $OPPONENTS \
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

    END_GEN=$(date +%s)
    GEN_DURATION=$(( END_GEN - START_GEN ))
    GEN_MIN=$(( GEN_DURATION / 60 ))

    avis_telegram "[$GEN] V12 10k matchups done (${GEN_MIN}m)"
    cleanup
done

TOTAL_END=$(date +%s)
TOTAL_DURATION=$(( TOTAL_END - TOTAL_START ))
TOTAL_HOURS=$(( TOTAL_DURATION / 3600 ))
TOTAL_REMAINDER=$(( TOTAL_DURATION % 3600 ))
TOTAL_MIN=$(( TOTAL_REMAINDER / 60 ))

avis_telegram "V12 10k benchmark DONE ($N_BATTLES games). Total: ${TOTAL_HOURS}h${TOTAL_MIN}m. Results in $OUT_BASE/ ($(date '+%H:%M'))"
