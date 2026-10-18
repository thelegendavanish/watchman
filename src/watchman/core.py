from __future__ import annotations

import ctypes
import fnmatch
import hashlib
import json
import os
import queue
import sqlite3
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

# ── Paths ─────────────────────────────────────────────────────────────────────

APP_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Watchman"
DEPLOYMENTS_DIR = APP_DIR / "deployments"

# ── Optional secure credential storage via keyring ────────────────────────────

try:
    import keyring as _keyring
    _HAS_KEYRING = True
except ImportError:
    _keyring = None  # type: ignore
    _HAS_KEYRING = False

_KEYRING_SERVICE = "Watchman"


def _keyring_key(name: str, field: str) -> str:
    return f"{name}:{field}"


def store_telegram_creds(name: str, token: str, chat_id: str) -> bool:
    """Store Telegram credentials securely if keyring is available."""
    if _HAS_KEYRING:
        _keyring.set_password(_KEYRING_SERVICE, _keyring_key(name, "telegram_token"), token)
        _keyring.set_password(_KEYRING_SERVICE, _keyring_key(name, "telegram_chat_id"), chat_id)
        return True
    return False


def get_telegram_creds(name: str, config: dict) -> tuple[str, str]:
    """Return (token, chat_id). Prefers keyring; falls back to config file."""
    if _HAS_KEYRING:
        token = _keyring.get_password(_KEYRING_SERVICE, _keyring_key(name, "telegram_token")) or ""
        chat_id = _keyring.get_password(_KEYRING_SERVICE, _keyring_key(name, "telegram_chat_id")) or ""
        if token:
            return token, chat_id
    return config.get("telegram_bot_token", ""), config.get("telegram_chat_id", "")


def delete_telegram_creds(name: str) -> bool:
    """Remove Telegram credentials from keyring."""
    if not _HAS_KEYRING:
        return False
    try:
        _keyring.delete_password(_KEYRING_SERVICE, _keyring_key(name, "telegram_token"))
        _keyring.delete_password(_KEYRING_SERVICE, _keyring_key(name, "telegram_chat_id"))
    except Exception:
        pass
    return True


# ── Utilities ─────────────────────────────────────────────────────────────────

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def deployment_dir(name: str) -> Path:
    if not name or any(
        c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
        for c in name
    ):
        raise ValueError(
            "Deployment names may contain only letters, numbers, hyphens and underscores."
        )
    return DEPLOYMENTS_DIR / name


def load_config(name: str) -> tuple[Path, dict]:
    folder = deployment_dir(name)
    cfg_path = folder / "config.json"
    if not cfg_path.exists():
        raise FileNotFoundError(
            f"Deployment '{name}' does not exist. Run: watchman init {name}"
        )
    return folder, json.loads(cfg_path.read_text(encoding="utf-8"))


def save_config(folder: Path, config: dict) -> None:
    path = folder / "config.json"
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(config, indent=2), encoding="utf-8")
    tmp.replace(path)


# ── Database ──────────────────────────────────────────────────────────────────

_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp        TEXT NOT NULL,
    event_type       TEXT NOT NULL,
    path             TEXT NOT NULL,
    destination_path TEXT,
    sha256           TEXT,
    details          TEXT,
    prev_event_hash  TEXT
);

CREATE TABLE IF NOT EXISTS baselines (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    scanned TEXT NOT NULL,
    path    TEXT NOT NULL,
    sha256  TEXT NOT NULL
);
"""


def db_connect(folder: Path) -> sqlite3.Connection:
    """Open (or create) the deployment SQLite database, applying schema migrations."""
    db = sqlite3.connect(
        folder / "events.sqlite3",
        timeout=10,
        check_same_thread=False,
    )
    db.executescript(_SCHEMA)
    try:
        db.execute("ALTER TABLE events ADD COLUMN prev_event_hash TEXT")
        db.commit()
    except sqlite3.OperationalError:
        pass  # column already present
    return db


def _chain_hash(row: tuple) -> str:
    """SHA-256 over the serialised contents of an event row for tamper-evidence chaining."""
    return hashlib.sha256("|".join(str(x or "") for x in row).encode()).hexdigest()


# ── File hashing ──────────────────────────────────────────────────────────────

def sha256_file(path: str) -> Optional[str]:
    """Return the hex SHA-256 of a file, or None on permission/IO error."""
    try:
        p = Path(path)
        if not p.is_file():
            return None
        h = hashlib.sha256()
        with p.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()
    except (OSError, PermissionError):
        return None


# ── Baseline integrity scan ───────────────────────────────────────────────────

def baseline_scan(folder: Path, config: dict) -> int:
    """Hash every file under protected_paths and store in the baselines table."""
    paths = config.get("protected_paths", [])
    scanned_at = utc_now()
    count = 0
    with db_connect(folder) as db:
        db.execute("DELETE FROM baselines")
        db.commit()
        for raw in paths:
            p = Path(raw).expanduser().resolve()
            if not p.exists():
                print(f"[WARN] Skipping unavailable path: {p}")
                continue
            for f in p.rglob("*"):
                if not f.is_file():
                    continue
                digest = sha256_file(str(f))
                if digest:
                    db.execute(
                        "INSERT INTO baselines(scanned, path, sha256) VALUES (?,?,?)",
                        (scanned_at, str(f), digest),
                    )
                    count += 1
        db.commit()
    return count


def verify_baseline(folder: Path, config: dict) -> list[dict]:
    """Compare the live filesystem against the stored baseline."""
    with db_connect(folder) as db:
        rows = db.execute("SELECT path, sha256 FROM baselines").fetchall()

    if not rows:
        return []

    baseline: dict[str, str] = {r[0]: r[1] for r in rows}
    changes: list[dict] = []

    for path_str, expected in baseline.items():
        p = Path(path_str)
        if not p.exists():
            changes.append(
                {"status": "MISSING", "path": path_str, "expected": expected, "actual": None}
            )
        else:
            actual = sha256_file(path_str)
            if actual != expected:
                changes.append(
                    {"status": "MODIFIED", "path": path_str, "expected": expected, "actual": actual}
                )

    for raw in config.get("protected_paths", []):
        p = Path(raw).expanduser().resolve()
        if not p.exists():
            continue
        for f in p.rglob("*"):
            if f.is_file() and str(f) not in baseline:
                changes.append(
                    {"status": "NEW", "path": str(f), "expected": None, "actual": sha256_file(str(f))}
                )

    return changes


# ── Event recorder ────────────────────────────────────────────────────────────

class _WriteWorker(threading.Thread):
    """Dedicated background thread that serialises all SQLite writes."""

    def __init__(self, db: sqlite3.Connection):
        super().__init__(daemon=True, name="wm-db-writer")
        self._db = db
        self._q: queue.Queue = queue.Queue()

    def submit(self, row: tuple) -> None:
        self._q.put(row)

    def stop(self) -> None:
        self._q.put(None)

    def run(self) -> None:
        while True:
            item = self._q.get()
            if item is None:
                break
            ts, event_type, src, dest, digest, details = item
            try:
                prev = self._db.execute(
                    "SELECT id,timestamp,event_type,path,destination_path,sha256,prev_event_hash "
                    "FROM events ORDER BY id DESC LIMIT 1"
                ).fetchone()
                prev_hash = _chain_hash(prev) if prev else None
                self._db.execute(
                    "INSERT INTO events"
                    "(timestamp,event_type,path,destination_path,sha256,details,prev_event_hash)"
                    " VALUES (?,?,?,?,?,?,?)",
                    (ts, event_type, src, dest, digest, details, prev_hash),
                )
                self._db.commit()
            except sqlite3.Error as exc:
                print(f"[ERROR] DB write failed: {exc}")


class EventRecorder(FileSystemEventHandler):
    """Watchdog handler: debounces, hashes (non-blocking), writes to DB, sends Telegram."""

    _DEBOUNCE_S = 0.4

    def __init__(self, name: str, folder: Path, config: dict):
        self.name = name
        self.folder = folder
        self.config = config
        self._lock = threading.Lock()
        self._last_seen: dict[tuple, float] = {}
        self._exclude: list[str] = config.get("exclude_patterns", [])
        self._executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="wm-hash")
        self._db = db_connect(folder)
        self._writer = _WriteWorker(self._db)
        self._writer.start()

    def _excluded(self, path: str) -> bool:
        name = os.path.basename(path)
        return any(fnmatch.fnmatch(name, pat) for pat in self._exclude)

    def on_any_event(self, event) -> None:
        if event.event_type not in {"created", "modified", "deleted", "moved"}:
            return
        src = os.path.abspath(event.src_path)
        dest = (
            os.path.abspath(event.dest_path)
            if getattr(event, "dest_path", None)
            else None
        )
        if os.path.isdir(src) and event.event_type == "modified":
            return
        if self._excluded(src):
            return

        now = time.monotonic()
        key = (event.event_type, src, dest)
        with self._lock:
            if now - self._last_seen.get(key, 0) < self._DEBOUNCE_S:
                return
            self._last_seen[key] = now

        details = "directory" if getattr(event, "is_directory", False) else "file"

        if event.event_type in {"created", "modified", "moved"}:
            self._executor.submit(self._hash_then_record, src, dest, event.event_type, details)
        else:
            self._do_record(None, src, dest, event.event_type, details)

    def _hash_then_record(self, src: str, dest: Optional[str], event_type: str, details: str) -> None:
        digest = sha256_file(src)
        self._do_record(digest, src, dest, event_type, details)

    def _do_record(self, digest: Optional[str], src: str, dest: Optional[str],
                   event_type: str, details: str) -> None:
        ts = utc_now()
        self._writer.submit((ts, event_type, src, dest, digest, details))

        label = f"{event_type.upper()}: {src}"
        if dest:
            label += f" -> {dest}"
        if digest:
            label += f" [sha256:{digest[:12]}...]"
        print(f"[{ts}] {label}")

        self._telegram(event_type, src, dest, digest, ts)

    def _telegram(self, event_type: str, path: str, dest: Optional[str],
                  digest: Optional[str], ts: str) -> None:
        token, chat_id = get_telegram_creds(self.name, self.config)
        if not token or not chat_id:
            return
        msg = (
            f"🔔 Watchman Alert\n"
            f"Deployment: {self.name}\n"
            f"Event: {event_type.upper()}\n"
            f"Path: {path}"
        )
        if dest:
            msg += f"\nDestination: {dest}"
        if digest:
            msg += f"\nSHA-256: {digest}"
        msg += f"\nTime: {ts}"
        try:
            requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": msg},
                timeout=5,
            ).raise_for_status()
        except requests.RequestException as exc:
            print(f"[WARN] Telegram delivery failed: {exc}")

    def close(self) -> None:
        self._executor.shutdown(wait=True)
        self._writer.stop()
        self._writer.join(timeout=5)
        self._db.close()


# ── Monitor runner ────────────────────────────────────────────────────────────

def _pid_file(folder: Path) -> Path:
    return folder / "monitor.pid"


def _log_file(folder: Path) -> Path:
    return folder / "monitor.log"


def run_monitor(name: str, background: bool = False) -> None:
    folder, config = load_config(name)
    paths = config.get("protected_paths", [])
    if not paths:
        raise RuntimeError(
            f"Deployment '{name}' has no protected folders. "
            f"Add one with: watchman watch add {name} <path>"
        )

    if background:
        _start_background(name, folder)
        return

    observer = Observer()
    handler = EventRecorder(name, folder, config)
    active = 0
    for raw in paths:
        p = Path(raw).expanduser().resolve()
        if not p.is_dir():
            print(f"[WARN] Skipping unavailable directory: {p}")
            continue
        observer.schedule(handler, str(p), recursive=True)
        active += 1
        print(f"[WATCHING] {p}")

    if not active:
        handler.close()
        raise RuntimeError("No configured protected directories are currently accessible.")

    observer.start()
    print(f"Watchman monitoring deployment '{name}'. Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping Watchman...")
    finally:
        observer.stop()
        observer.join(timeout=5)
        handler.close()
        print("Monitoring stopped.")


def _start_background(name: str, folder: Path) -> None:
    """Spawn a detached monitoring process and write its PID to disk."""
    pid_path = _pid_file(folder)
    if pid_path.exists():
        existing_pid = int(pid_path.read_text().strip())
        if _pid_alive(existing_pid):
            print(
                f"[WARN] A background monitor is already running for '{name}' "
                f"(PID {existing_pid}).\n"
                f"Stop it first with: watchman stop {name}"
            )
            return

    log_path = _log_file(folder)
    DETACHED_PROCESS = 0x00000008
    CREATE_NEW_PROCESS_GROUP = 0x00000200

    with open(log_path, "a", encoding="utf-8") as log_fh:
        proc = subprocess.Popen(
            [sys.executable, "-m", "watchman", "start", name],
            creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
            stdout=log_fh,
            stderr=subprocess.STDOUT,
            close_fds=True,
        )

    pid_path.write_text(str(proc.pid), encoding="utf-8")
    print(f"Watchman background monitor started for '{name}' (PID {proc.pid}).")
    print(f"Log : {log_path}")
    print(f"Stop: watchman stop {name}")
    print(f"Tail: watchman logs {name}")


def stop_monitor(name: str) -> None:
    """Terminate a background monitor by PID."""
    folder = deployment_dir(name)
    pid_path = _pid_file(folder)
    if not pid_path.exists():
        raise FileNotFoundError(
            f"No background monitor PID file found for '{name}'. "
            "The monitor may not be running in the background."
        )
    pid = int(pid_path.read_text().strip())
    if not _pid_alive(pid):
        pid_path.unlink(missing_ok=True)
        print(f"Process {pid} is no longer running (PID file cleaned up).")
        return
    _kill_pid(pid)
    pid_path.unlink(missing_ok=True)
    print(f"Stopped background monitor for '{name}' (PID {pid}).")


def monitor_status(name: str) -> dict:
    """Return status information about a deployment's background monitor."""
    folder = deployment_dir(name)
    pid_path = _pid_file(folder)
    if not pid_path.exists():
        return {"running": False, "pid": None, "log": None}
    pid = int(pid_path.read_text().strip())
    alive = _pid_alive(pid)
    if not alive:
        pid_path.unlink(missing_ok=True)
    log = _log_file(folder)
    return {"running": alive, "pid": pid if alive else None, "log": str(log) if log.exists() else None}


# ── Windows process helpers ───────────────────────────────────────────────────

def _pid_alive(pid: int) -> bool:
    try:
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259
        handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return False
        code = ctypes.c_ulong()
        ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
        ctypes.windll.kernel32.CloseHandle(handle)
        return code.value == STILL_ACTIVE
    except Exception:
        return False


def _kill_pid(pid: int) -> None:
    PROCESS_TERMINATE = 0x0001
    handle = ctypes.windll.kernel32.OpenProcess(PROCESS_TERMINATE, False, pid)
    if not handle:
        raise RuntimeError(f"Cannot open process {pid}. It may have already exited.")
    ok = ctypes.windll.kernel32.TerminateProcess(handle, 1)
    ctypes.windll.kernel32.CloseHandle(handle)
    if not ok:
        raise RuntimeError(f"TerminateProcess failed for PID {pid}.")
