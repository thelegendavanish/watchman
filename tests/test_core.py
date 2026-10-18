"""
Tests for watchman.core — no real filesystem watches, no network calls.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import time
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_deployment(tmp_path: Path, name: str = "test") -> tuple[Path, dict]:
    """Create a minimal deployment directory and config."""
    from watchman.core import db_connect, save_config

    folder = tmp_path / name
    folder.mkdir(parents=True)
    config = {
        "name": name,
        "protected_paths": [str(tmp_path / "watched")],
        "exclude_patterns": [],
        "telegram_bot_token": "",
        "telegram_chat_id": "",
        "startup_enabled": False,
    }
    save_config(folder, config)
    db_connect(folder).close()
    return folder, config


# ---------------------------------------------------------------------------
# utc_now
# ---------------------------------------------------------------------------

def test_utc_now_format():
    from watchman.core import utc_now
    ts = utc_now()
    assert "T" in ts
    assert ts.endswith("+00:00") or ts.endswith("Z") or "+" in ts or ts[-6] in ("+", "-")


# ---------------------------------------------------------------------------
# deployment_dir
# ---------------------------------------------------------------------------

def test_deployment_dir_valid():
    from watchman.core import DEPLOYMENTS_DIR, deployment_dir
    d = deployment_dir("my-deploy_01")
    assert d == DEPLOYMENTS_DIR / "my-deploy_01"


@pytest.mark.parametrize("bad_name", ["", "has space", "path/traversal", "../escape", "a$b"])
def test_deployment_dir_invalid(bad_name):
    from watchman.core import deployment_dir
    with pytest.raises(ValueError):
        deployment_dir(bad_name)


# ---------------------------------------------------------------------------
# save_config / load_config
# ---------------------------------------------------------------------------

def test_save_load_config(tmp_path):
    from watchman.core import load_config, save_config, DEPLOYMENTS_DIR
    import os

    # Temporarily redirect DEPLOYMENTS_DIR so load_config finds the folder.
    original = DEPLOYMENTS_DIR
    import watchman.core as _core
    _core.DEPLOYMENTS_DIR = tmp_path

    folder = tmp_path / "mydeployment"
    folder.mkdir()
    cfg = {"name": "mydeployment", "protected_paths": ["/some/path"]}
    save_config(folder, cfg)

    _, loaded = load_config("mydeployment")
    assert loaded["name"] == "mydeployment"
    assert loaded["protected_paths"] == ["/some/path"]

    _core.DEPLOYMENTS_DIR = original  # restore


def test_save_config_atomic(tmp_path):
    """Ensure the .json.tmp file is gone after save."""
    from watchman.core import save_config

    folder = tmp_path
    save_config(folder, {"x": 1})
    assert not (tmp_path / "config.json.tmp").exists()
    assert (tmp_path / "config.json").exists()


# ---------------------------------------------------------------------------
# db_connect / schema
# ---------------------------------------------------------------------------

def test_db_schema_created(tmp_path):
    from watchman.core import db_connect

    db = db_connect(tmp_path)
    tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert "events" in tables
    assert "baselines" in tables
    db.close()


def test_db_connect_idempotent(tmp_path):
    """Calling db_connect twice on the same folder must not fail."""
    from watchman.core import db_connect

    db_connect(tmp_path).close()
    db_connect(tmp_path).close()


def test_db_migration_adds_column(tmp_path):
    """If prev_event_hash column is missing, db_connect should add it without error."""
    from watchman.core import db_connect

    # Create DB without the new column.
    db = sqlite3.connect(tmp_path / "events.sqlite3")
    db.execute("""CREATE TABLE events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        event_type TEXT NOT NULL,
        path TEXT NOT NULL,
        destination_path TEXT,
        sha256 TEXT,
        details TEXT
    )""")
    db.commit()
    db.close()

    # db_connect should add the column gracefully.
    db = db_connect(tmp_path)
    cols = {row[1] for row in db.execute("PRAGMA table_info(events)").fetchall()}
    assert "prev_event_hash" in cols
    db.close()


# ---------------------------------------------------------------------------
# sha256_file
# ---------------------------------------------------------------------------

def test_sha256_file_correct(tmp_path):
    from watchman.core import sha256_file

    f = tmp_path / "hello.txt"
    f.write_bytes(b"hello world")
    expected = hashlib.sha256(b"hello world").hexdigest()
    assert sha256_file(str(f)) == expected


def test_sha256_file_missing(tmp_path):
    from watchman.core import sha256_file

    result = sha256_file(str(tmp_path / "nonexistent.txt"))
    assert result is None


def test_sha256_file_directory(tmp_path):
    from watchman.core import sha256_file

    result = sha256_file(str(tmp_path))
    assert result is None


# ---------------------------------------------------------------------------
# _chain_hash
# ---------------------------------------------------------------------------

def test_chain_hash_deterministic():
    from watchman.core import _chain_hash

    row = (1, "2024-01-01T00:00:00+00:00", "created", "/a/b.txt", None, "abc123", None)
    h1 = _chain_hash(row)
    h2 = _chain_hash(row)
    assert h1 == h2
    assert len(h1) == 64


def test_chain_hash_different_for_different_rows():
    from watchman.core import _chain_hash

    r1 = (1, "2024-01-01T00:00:00+00:00", "created", "/a.txt", None, None, None)
    r2 = (2, "2024-01-01T00:00:01+00:00", "deleted", "/a.txt", None, None, None)
    assert _chain_hash(r1) != _chain_hash(r2)


# ---------------------------------------------------------------------------
# baseline_scan / verify_baseline
# ---------------------------------------------------------------------------

def test_baseline_scan_counts_files(tmp_path):
    from watchman.core import baseline_scan

    watched = tmp_path / "watched"
    watched.mkdir()
    (watched / "a.txt").write_text("aaa")
    (watched / "b.txt").write_text("bbb")
    sub = watched / "sub"
    sub.mkdir()
    (sub / "c.txt").write_text("ccc")

    folder = tmp_path / "deploy"
    folder.mkdir()
    config = {"protected_paths": [str(watched)]}
    count = baseline_scan(folder, config)
    assert count == 3


def test_verify_baseline_clean(tmp_path):
    from watchman.core import baseline_scan, verify_baseline

    watched = tmp_path / "watched"
    watched.mkdir()
    (watched / "x.txt").write_text("data")

    folder = tmp_path / "deploy"
    folder.mkdir()
    config = {"protected_paths": [str(watched)]}
    baseline_scan(folder, config)
    changes = verify_baseline(folder, config)
    assert changes == []


def test_verify_baseline_detects_modification(tmp_path):
    from watchman.core import baseline_scan, verify_baseline

    watched = tmp_path / "watched"
    watched.mkdir()
    f = watched / "x.txt"
    f.write_text("original")

    folder = tmp_path / "deploy"
    folder.mkdir()
    config = {"protected_paths": [str(watched)]}
    baseline_scan(folder, config)

    f.write_text("tampered!")
    changes = verify_baseline(folder, config)
    assert any(c["status"] == "MODIFIED" for c in changes)


def test_verify_baseline_detects_missing(tmp_path):
    from watchman.core import baseline_scan, verify_baseline

    watched = tmp_path / "watched"
    watched.mkdir()
    f = watched / "x.txt"
    f.write_text("data")

    folder = tmp_path / "deploy"
    folder.mkdir()
    config = {"protected_paths": [str(watched)]}
    baseline_scan(folder, config)

    f.unlink()
    changes = verify_baseline(folder, config)
    assert any(c["status"] == "MISSING" for c in changes)


def test_verify_baseline_detects_new_file(tmp_path):
    from watchman.core import baseline_scan, verify_baseline

    watched = tmp_path / "watched"
    watched.mkdir()
    (watched / "old.txt").write_text("old")

    folder = tmp_path / "deploy"
    folder.mkdir()
    config = {"protected_paths": [str(watched)]}
    baseline_scan(folder, config)

    (watched / "new.txt").write_text("new file added after baseline")
    changes = verify_baseline(folder, config)
    assert any(c["status"] == "NEW" for c in changes)


def test_verify_baseline_empty_returns_empty(tmp_path):
    from watchman.core import verify_baseline

    folder = tmp_path / "deploy"
    folder.mkdir()
    from watchman.core import db_connect
    db_connect(folder).close()
    config = {"protected_paths": []}
    assert verify_baseline(folder, config) == []


# ---------------------------------------------------------------------------
# _WriteWorker — threaded DB writes
# ---------------------------------------------------------------------------

def test_write_worker_records_events(tmp_path):
    from watchman.core import _WriteWorker, db_connect

    db = db_connect(tmp_path)
    worker = _WriteWorker(db)
    worker.start()

    worker.submit(("2024-01-01T00:00:00+00:00", "created", "/a.txt", None, "abc", "file"))
    worker.submit(("2024-01-01T00:00:01+00:00", "deleted", "/a.txt", None, None, "file"))
    worker.stop()
    worker.join(timeout=3)

    rows = db.execute("SELECT event_type FROM events ORDER BY id").fetchall()
    db.close()
    types = [r[0] for r in rows]
    assert types == ["created", "deleted"]


# ---------------------------------------------------------------------------
# _pid_alive
# ---------------------------------------------------------------------------

def test_pid_alive_current_process():
    from watchman.core import _pid_alive
    import os
    assert _pid_alive(os.getpid()) is True


def test_pid_alive_bogus_pid():
    from watchman.core import _pid_alive
    # PID 0 is the System Idle Process on Windows and is never a user process.
    assert _pid_alive(99999999) is False
