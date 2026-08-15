"""Start / wait / stop local Showdown from inside train and eval entrypoints.

Wraps ``src/p00_core/scripts/launch_custom_servers.sh``. Never pkill's other
jobs; only processes this session started are stopped on exit.
"""

from __future__ import annotations

import atexit
import logging
import os
import re
import signal
import socket
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from .._bootstrap import repo_root
from ..constants import BASE_PORT, DEFAULT_PORTS

_QUIET_LOGS = False
_BENIGN_SHOWDOWN = (
    "the-studio.json",
    "sample-teams.json",
    "mafia-logs.json",
    "lastbattle.txt",
)


class _ClosedWebsocketFilter(logging.Filter):
    """Drop poke-env's traceback when we kill Showdown on purpose."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
        except Exception:
            msg = str(record.msg)
        if "no close frame received or sent" in msg:
            return False
        if record.exc_info and record.exc_info[1] is not None:
            name = record.exc_info[1].__class__.__name__
            if name.startswith("ConnectionClosed"):
                return False
        return True


def quiet_showdown_client_logs() -> None:
    """Hide expected websocket teardown noise. Call in the parent and in SubprocVecEnv workers."""
    global _QUIET_LOGS
    if _QUIET_LOGS:
        return
    _QUIET_LOGS = True
    filt = _ClosedWebsocketFilter()
    root = logging.getLogger()
    root.addFilter(filt)
    for handler in root.handlers:
        handler.addFilter(filt)
    for name in (
        "poke_env",
        "websockets",
        "websockets.client",
        "websockets.asyncio",
        "websockets.asyncio.connection",
    ):
        log = logging.getLogger(name)
        log.setLevel(logging.CRITICAL)
        log.addFilter(filt)

    orig_exception = logging.Logger.exception

    def _exception(self, msg, *args, exc_info=True, **kwargs):
        err = msg if isinstance(msg, BaseException) else None
        text = str(msg)
        if (err is not None and err.__class__.__name__.startswith("ConnectionClosed")) or (
            "no close frame received or sent" in text
        ):
            return
        orig_exception(self, msg, *args, exc_info=exc_info, **kwargs)

    logging.Logger.exception = _exception

    try:
        from poke_env.ps_client.ps_client import PSClient
        from websockets.exceptions import ConnectionClosedError, ConnectionClosedOK
    except Exception:
        return

    orig_listen = PSClient.listen

    async def listen(self):
        try:
            await orig_listen(self)
        except (ConnectionClosedError, ConnectionClosedOK, ConnectionResetError, BrokenPipeError, OSError):
            return

    PSClient.listen = listen


async def close_ps_clients(*players) -> None:
    """Close poke-env websockets before killing Showdown so teardown is a clean close."""
    for player in players:
        if player is None:
            continue
        try:
            websocket = getattr(player, "websocket", None)
            if websocket is not None:
                await player.stop_listening()
        except Exception:
            pass


_LAUNCHER = repo_root() / "src" / "p00_core" / "scripts" / "launch_custom_servers.sh"
_PID_RE = re.compile(r"\[Port (\d+)\].*PID (\d+)")
_REUSE_RE = re.compile(r"\[Port (\d+)\].*already listening")


def parse_ports(ports: list[int] | None) -> list[int]:
    """``None`` → 8000–8003. A single int 1–10 is a count from 8000. Else an explicit consecutive list."""
    if not ports:
        return list(DEFAULT_PORTS)
    if len(ports) == 1 and 1 <= ports[0] <= 10:
        return list(range(BASE_PORT, BASE_PORT + ports[0]))
    if any(p < 1024 for p in ports):
        raise SystemExit(f"Invalid --ports {ports}. Use a count 1–10 or ports ≥ 8000.")
    expected = list(range(ports[0], ports[0] + len(ports)))
    if ports != expected:
        raise SystemExit(
            f"--ports must be consecutive (launcher uses BASE_PORT+i). Got {ports}."
        )
    if len(ports) > 10:
        raise SystemExit("At most 10 Showdown servers (launcher limit).")
    return ports


def pids_on_port(port: int) -> list[int]:
    """PIDs listening on ``port``. TCP-up is not the same as a working Showdown."""
    pids: set[int] = set()
    try:
        out = subprocess.check_output(
            ["ss", "-lptn", f"sport = :{port}"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        pids.update(int(x) for x in re.findall(r"pid=(\d+)", out))
    except (FileNotFoundError, subprocess.CalledProcessError, OSError):
        pass
    if not pids:
        try:
            out = subprocess.check_output(
                ["fuser", f"{port}/tcp"],
                text=True,
                stderr=subprocess.STDOUT,
            )
            pids.update(int(x) for x in re.findall(r"\d+", out))
        except (FileNotFoundError, subprocess.CalledProcessError, OSError):
            pass
    if not pids:
        try:
            out = subprocess.check_output(
                ["lsof", "-t", f"-iTCP:{port}", "-sTCP:LISTEN"],
                text=True,
                stderr=subprocess.DEVNULL,
            )
            pids.update(int(x) for x in out.split() if x.isdigit())
        except (FileNotFoundError, subprocess.CalledProcessError, OSError):
            pass
    return sorted(pids)


def kill_port_listeners(ports: list[int]) -> list[int]:
    """SIGTERM then SIGKILL whatever is bound to ``ports``. Used so train does not reuse a wedged eval server."""
    killed: list[int] = []
    for port in ports:
        for pid in pids_on_port(port):
            try:
                os.kill(pid, signal.SIGTERM)
                killed.append(pid)
            except (ProcessLookupError, PermissionError, OSError):
                pass
    if not killed:
        return []
    time.sleep(0.6)
    for pid in killed:
        try:
            os.kill(pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError, OSError):
            pass
    time.sleep(0.4)
    deadline = time.time() + 5.0
    while time.time() < deadline and any(websocket_up(p, timeout=0.3) for p in ports):
        time.sleep(0.2)
    print(f"Killed stale Showdown listeners pids={killed} on ports {ports}.", flush=True)
    return killed


def websocket_up(port: int, timeout: float = 2.0) -> bool:
    """HTTP Upgrade to ``/showdown/websocket`` — TCP listen is not enough."""
    try:
        sock = socket.create_connection(("127.0.0.1", port), timeout=timeout)
    except OSError:
        return False
    try:
        sock.settimeout(timeout)
        key = "dGhlIHNhbXBsZSBub25jZQ=="
        req = (
            f"GET /showdown/websocket HTTP/1.1\r\n"
            f"Host: 127.0.0.1:{port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n"
            "\r\n"
        )
        sock.sendall(req.encode("ascii"))
        chunks: list[bytes] = []
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                data = sock.recv(2048)
            except OSError:
                break
            if not data:
                break
            chunks.append(data)
            blob = b"".join(chunks)
            if b"\r\n\r\n" in blob:
                break
        blob = b"".join(chunks)
        head = blob.split(b"\r\n", 1)[0].decode("latin1", errors="replace")
        return "101" in head or b"Upgrade" in blob
    except OSError:
        return False
    finally:
        try:
            sock.close()
        except OSError:
            pass


def wait_until_ready(ports: list[int], timeout: float | None = None) -> None:
    if timeout is None:
        timeout = 30.0 + 3.0 * len(ports)
    deadline = time.time() + timeout
    pending = set(ports)
    while pending and time.time() < deadline:
        ready = {p for p in pending if websocket_up(p)}
        pending -= ready
        if pending:
            time.sleep(0.4)
    if pending:
        raise TimeoutError(
            f"Showdown websocket not up on ports {sorted(pending)} "
            f"(ws://127.0.0.1:<port>/showdown/websocket). Waited {timeout:.0f}s."
        )


@dataclass
class ShowdownSession:
    ports: list[int]
    started_pids: list[int] = field(default_factory=list)
    launcher_proc: subprocess.Popen | None = None
    _stopped: bool = False

    def stop(self) -> None:
        if self._stopped:
            return
        self._stopped = True
        pids = list(self.started_pids)
        proc = self.launcher_proc
        if proc is not None and proc.poll() is None:
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except (ProcessLookupError, PermissionError, OSError):
                proc.terminate()
            try:
                proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except (ProcessLookupError, PermissionError, OSError):
                    proc.kill()
        for pid in pids:
            try:
                os.kill(pid, signal.SIGTERM)
            except (ProcessLookupError, PermissionError, OSError):
                pass
        time.sleep(0.3)
        for pid in pids:
            try:
                os.kill(pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError, OSError):
                pass
        if pids or proc is not None:
            print(f"Stopped Showdown started by this run (pids={pids}). Reused ports left running.")


_ACTIVE: ShowdownSession | None = None


def _atexit_stop() -> None:
    if _ACTIVE is not None:
        _ACTIVE.stop()


def ensure_showdown(ports: list[int] | None = None, *, restart: bool = False) -> ShowdownSession:
    """Reuse healthy websockets; otherwise start missing consecutive ports via the stock launcher.

    ``restart=True`` (train) kills listeners on those ports first. Eval leaves
    8000–8003 up; a later 8-port train then reuses a wedged 8004/8005 and dies
    with ``TimeoutError: Agent is not challenging``.
    """
    global _ACTIVE
    quiet_showdown_client_logs()
    ports = parse_ports(ports)
    if restart:
        kill_port_listeners(ports)
    already = [p for p in ports if websocket_up(p)]
    missing = [p for p in ports if p not in already]
    if not missing:
        print(f"Reusing healthy Showdown on ports {ports}.")
        session = ShowdownSession(ports=ports)
        _ACTIVE = session
        return session

    if not _LAUNCHER.is_file():
        raise FileNotFoundError(f"Missing launcher: {_LAUNCHER}")

    print(f"Starting Showdown via {_LAUNCHER.relative_to(repo_root())} "
          f"count={len(ports)} base={ports[0]} (missing={missing}).")
    env = os.environ.copy()
    proc = subprocess.Popen(
        ["bash", str(_LAUNCHER), str(len(ports)), str(ports[0])],
        cwd=str(repo_root()),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
        text=True,
        start_new_session=True,
        bufsize=1,
    )
    started_pids: list[int] = []
    log_lines: list[str] = []

    def _drain() -> None:
        assert proc.stdout is not None
        for line in proc.stdout:
            log_lines.append(line)
            if "CRASH: Error: ENOENT" in line and any(name in line for name in _BENIGN_SHOWDOWN):
                continue
            sys.stdout.write(line)
            sys.stdout.flush()
            m = _PID_RE.search(line)
            if m:
                started_pids.append(int(m.group(2)))

    reader = threading.Thread(target=_drain, daemon=True)
    reader.start()

    # The launcher sleeps ~2s per new server + 3s. Bound the wait.
    wait_until_ready(ports, timeout=30 + 4 * len(ports))
    reader.join(timeout=2.0)

    session = ShowdownSession(ports=ports, started_pids=started_pids, launcher_proc=proc)
    _ACTIVE = session
    atexit.register(_atexit_stop)
    return session


def server_configuration(port: int):
    from poke_env.ps_client.server_configuration import LocalhostServerConfiguration

    return LocalhostServerConfiguration._replace(
        websocket_url=f"ws://127.0.0.1:{port}/showdown/websocket"
    )
