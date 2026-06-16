# Benchmark Performance Tuning Guide

## Architecture: What Runs Where

Each **port** spawns 2 processes:
1. **Node.js** — Pokémon Showdown server (single-threaded, handles battle logic)
2. **Python** — Worker process (asyncio, sends/receives moves)

Each Python worker runs `concurrency` battles simultaneously against its assigned Node.js server via websockets.

```
Port 8000: [Node.js server] <--websocket--> [Python worker: 30 async battles]
Port 8001: [Node.js server] <--websocket--> [Python worker: 30 async battles]
...
Port 8007: [Node.js server] <--websocket--> [Python worker: 30 async battles]
```

Total parallel battles = `ports × concurrency`.

---

## Bottleneck Analysis

| Resource | Bottleneck | Why |
|----------|-----------|-----|
| **CPU cores** | Limits number of ports | Each port = 2 processes (Node + Python). Ports > cores/2 causes context-switching overhead |
| **Node.js single-thread** | Limits concurrency per port | One Showdown server processes all battles sequentially. Above ~30-35, turn processing lags |
| **RAM** | Limits total scale | Each port uses ~2 GB (Node + Python + battle state). More ports = more RAM |
| **GPU** | Not used | Heuristic agents are CPU-only. GPU only matters for LLM agents (Ollama) |

---

## Optimal Configuration by Hardware

| CPU | RAM | Ports | Concurrency | Total Battles | Notes |
|-----|-----|-------|-------------|---------------|-------|
| 4 cores / 8 threads | 16 GB | 4 | 15 | 60 | Conservative, safe |
| 6 cores / 12 threads | 16 GB | 6 | 20 | 120 | Good balance |
| 8 cores / 16 threads | 32 GB | 8 | 25-30 | 200-240 | Near-optimal |
| 16 cores / 32 threads | 64 GB | 16 | 25 | 400 | Diminishing returns past this |

### Formula

```
optimal_ports = min(physical_cores, RAM_GB / 2)
optimal_concurrency = 25-30 (Node.js hard limit)
```

---

## Why Not More Ports Than Cores?

Each port creates 2 OS processes (Node.js + Python). With 8 cores / 16 threads:
- 8 ports = 16 processes = 1 per thread (perfect)
- 16 ports = 32 processes = 2 per thread (context-switching, slower)

The OS scheduler forces processes to share CPU time, introducing latency instead of parallelism.

---

## Why Not More Than 30 Concurrency?

The Node.js Showdown server is **single-threaded**. It processes battles in a loop:

```
while (messages_pending) {
    process_one_turn();  // ~1-5ms per turn
}
```

With 30 concurrent battles, each averaging 20 turns × 2 players = ~1,200 messages per round of battles. The server handles this in real-time.

At 40+, the message queue backs up → turns take longer → Python workers hit timeouts → wasted compute retrying failed batches.

---

## Reference Configuration (Ryzen 5700X3D, 32 GB DDR4)

```bash
PORTS=8          # 8 cores = 8 ports (fills 16 threads with Node+Python pairs)
CONCURRENCY=30   # ~240 parallel battles, ~20-22 GB RAM, CPU near 100%
```

Observed metrics:
- RAM: ~16-22 GB (well under 32 GB limit)
- CPU: 90-100% all cores
- Temperature: <67°C per core (Noctua cooler)
- Swap: 0 usage (8 GB available, untouched)

---

## Time Estimates (10k games per matchup)

With 14 agents × 14 opponents = 196 matchups per gen:

| Config | Games/sec | Time per gen | All 9 gens |
|--------|-----------|-------------|------------|
| 4 ports × 10 conc | ~12 | ~45h | ~17 days |
| 8 ports × 20 conc | ~25 | ~22h | ~8 days |
| 8 ports × 30 conc | ~35 | ~16h | ~6 days |

These are estimates — actual speed depends on battle length (Gen 1 is faster, Gen 9 is slower due to more complex mechanics).

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| RAM > 26 GB | Too much concurrency | Reduce to `CONCURRENCY=25` |
| Timeout warnings in log | Node.js overloaded | Reduce to `CONCURRENCY=25` |
| CPU < 80% | Not enough parallelism | Increase `CONCURRENCY` by 5 |
| Temperature > 85°C | Sustained thermal load | Reduce `PORTS` by 2 |
| "Port busy" errors | Leftover servers | Run `pkill -f pokemon-showdown` and wait 5s |
