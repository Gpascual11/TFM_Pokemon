# p05_scripts: Infrastructure and Utilities

This directory contains standalone scripts to manage the Pokémon Showdown environment and parallel server instances.

## Core Scripts

### 1. `p05_launch_custom_servers.sh` (Recommended)
This is a dynamic launcher that allows you to specify exactly how many parallel servers you want to run.
- **Port Mapping**: Starts at `8000` and goes up to `8000 + (N-1)`.
- **Validation**: Supports between 1 and 10 servers.
- **Cleanup**: Automatically kills any previous server processes and cleans up background jobs on exit.

### 2. `p05_start_fixed_servers.sh`
A legacy-style script that launches a fixed set of 6 servers (Ports 8000–8005). Useful for standard high-concurrency benchmarks.

---

## How to Run

### Dynamic Launch (1-10 servers)
```bash
# Launch 4 parallel servers
./src/p05_scripts/p05_launch_custom_servers.sh 4
```

### Fixed Launch (6 servers)
```bash
./src/p05_scripts/p05_start_fixed_servers.sh
```

---

## Technical Notes
- **Dependencies**: Requires `node` and a local copy of the `pokemon-showdown` repository.
- **Security**: Servers are launched with the `--no-security` flag to allow the Python client to connect without password authentication.
- **Exit**: Press `Ctrl+C` in the terminal running the script to gracefully shut down all background server processes.
