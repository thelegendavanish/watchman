from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

from .core import (
    APP_DIR,
    DEPLOYMENTS_DIR,
    _HAS_KEYRING,
    _log_file,
    db_connect,
    delete_telegram_creds,
    deployment_dir,
    get_telegram_creds,
    load_config,
    monitor_status,
    run_monitor,
    save_config,
    baseline_scan,
    stop_monitor,
    store_telegram_creds,
    verify_baseline,
)


# ── init ──────────────────────────────────────────────────────────────────────

def cmd_init(args) -> int:
    folder = deployment_dir(args.name)
    if folder.exists() and (folder / "config.json").exists():
        print(f"Deployment already exists: {args.name}")
        return 1
    folder.mkdir(parents=True, exist_ok=True)
    config = {
        "name": args.name,
        "protected_paths": [],
        "exclude_patterns": [],
        "telegram_bot_token": "",
        "telegram_chat_id": "",
        "startup_enabled": False,
    }
    save_config(folder, config)
    db_connect(folder).close()
    print(f"Created deployment '{args.name}' at {folder}")
    print(f"Next: watchman watch add {args.name} <folder-path>")
    print("Monitoring has NOT been started and startup has NOT been enabled.")
    return 0


# ── list ──────────────────────────────────────────────────────────────────────

def cmd_list(_args) -> int:
    DEPLOYMENTS_DIR.mkdir(parents=True, exist_ok=True)
    found = False
    for p in sorted(DEPLOYMENTS_DIR.iterdir()):
        cfg = p / "config.json"
        if not cfg.exists():
            continue
        found = True
        data = json.loads(cfg.read_text(encoding="utf-8"))
        status = monitor_status(p.name)
        running_tag = " [RUNNING]" if status["running"] else ""
        print(
            f"{p.name}: {len(data.get('protected_paths', []))} protected path(s); "
            f"startup={'enabled' if data.get('startup_enabled') else 'disabled'}"
            f"{running_tag}"
        )
    if not found:
        print("No deployments yet. Create one with: watchman init <name>")
    return 0


# ── watch add/remove/list ─────────────────────────────────────────────────────

def cmd_add(args) -> int:
    folder, cfg = load_config(args.name)
    path = Path(args.path).expanduser().resolve()
    if not path.exists() or not path.is_dir():
        print(f"Error: directory does not exist: {path}")
        return 2
    paths = cfg.setdefault("protected_paths", [])
    if str(path) in paths:
        print("That directory is already protected.")
        return 0
    paths.append(str(path))

    if args.exclude:
        existing = cfg.setdefault("exclude_patterns", [])
        for pat in args.exclude:
            if pat not in existing:
                existing.append(pat)
        print(f"Exclude patterns added: {args.exclude}")

    save_config(folder, cfg)
    print(f"Added protected directory: {path}")
    print(f"Run 'watchman start {args.name}' to begin monitoring.")
    return 0


def cmd_remove(args) -> int:
    folder, cfg = load_config(args.name)
    path = str(Path(args.path).expanduser().resolve())
    if path not in cfg.get("protected_paths", []):
        print("That path is not in this deployment.")
        return 2
    cfg["protected_paths"].remove(path)
    save_config(folder, cfg)
    print(f"Removed protected directory: {path}")
    return 0


def cmd_paths(args) -> int:
    _, cfg = load_config(args.name)
    paths = cfg.get("protected_paths", [])
    excludes = cfg.get("exclude_patterns", [])
    if not paths:
        print("No protected directories configured.")
    else:
        for p in paths:
            print(p)
    if excludes:
        print(f"\nExclude patterns: {', '.join(excludes)}")
    return 0


# ── start / stop / status ─────────────────────────────────────────────────────

def cmd_start(args) -> int:
    run_monitor(args.name, background=args.background)
    return 0


def cmd_stop(args) -> int:
    stop_monitor(args.name)
    return 0


def cmd_status(args) -> int:
    st = monitor_status(args.name)
    if st["running"]:
        print(f"Deployment '{args.name}': RUNNING (PID {st['pid']})")
        if st["log"]:
            print(f"Log file: {st['log']}")
    else:
        print(f"Deployment '{args.name}': NOT running in background")
    return 0


# ── logs ──────────────────────────────────────────────────────────────────────

def cmd_logs(args) -> int:
    folder, _ = load_config(args.name)
    db = db_connect(folder)
    rows = db.execute(
        "SELECT id,timestamp,event_type,path,destination_path,sha256 "
        "FROM events ORDER BY id DESC LIMIT ?",
        (args.limit,),
    ).fetchall()
    db.close()
    if not rows:
        print("No events recorded yet.")
        return 0
    for row in rows:
        ident, ts, typ, path, dest, digest = row
        line = f"#{ident} [{ts}] {typ.upper()} {path}"
        if dest:
            line += f" -> {dest}"
        if digest:
            line += f" SHA256={digest}"
        print(line)
    return 0


# ── scan / verify ─────────────────────────────────────────────────────────────

def cmd_scan(args) -> int:
    folder, config = load_config(args.name)
    print(f"Scanning all files under protected paths for '{args.name}'...")
    count = baseline_scan(folder, config)
    print(f"Baseline snapshot complete: {count} file(s) indexed.")
    return 0


def cmd_verify(args) -> int:
    folder, config = load_config(args.name)
    print(f"Verifying integrity for deployment '{args.name}'...")
    changes = verify_baseline(folder, config)
    if not changes:
        print("[OK] All files match the baseline. No changes detected.")
        return 0
    print(f"[WARNING] {len(changes)} discrepancy(ies) found:\n")
    for c in changes:
        status = c["status"]
        path = c["path"]
        if status == "MODIFIED":
            print(f"  MODIFIED  {path}")
            print(f"            expected : {c['expected']}")
            print(f"            actual   : {c['actual']}")
        elif status == "MISSING":
            print(f"  MISSING   {path}")
        elif status == "NEW":
            print(f"  NEW       {path}")
            if c["actual"]:
                print(f"            sha256   : {c['actual']}")
    return 1


# ── export ────────────────────────────────────────────────────────────────────

def cmd_export(args) -> int:
    import csv
    import io

    folder, _ = load_config(args.name)
    db = db_connect(folder)
    rows = db.execute(
        "SELECT id,timestamp,event_type,path,destination_path,sha256,details,prev_event_hash "
        "FROM events ORDER BY id"
    ).fetchall()
    db.close()

    columns = ["id", "timestamp", "event_type", "path", "destination_path",
               "sha256", "details", "prev_event_hash"]
    records = [dict(zip(columns, row)) for row in rows]

    if args.format == "json":
        output = json.dumps(records, indent=2)
    else:
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=columns)
        writer.writeheader()
        writer.writerows(records)
        output = buf.getvalue()

    if args.output:
        out_path = Path(args.output)
        out_path.write_text(output, encoding="utf-8")
        print(f"Exported {len(records)} event(s) to {out_path}")
    else:
        print(output)
    return 0


# ── clear ─────────────────────────────────────────────────────────────────────

def cmd_clear(args) -> int:
    folder, _ = load_config(args.name)
    if not args.yes:
        answer = input(
            f"This will permanently delete all events for deployment '{args.name}'. "
            "Type YES to confirm: "
        )
        if answer.strip() != "YES":
            print("Aborted.")
            return 1
    db = db_connect(folder)
    db.execute("DELETE FROM events")
    db.commit()
    db.close()
    print(f"Event log cleared for deployment '{args.name}'.")
    return 0


# ── telegram ──────────────────────────────────────────────────────────────────

def cmd_telegram(args) -> int:
    folder, cfg = load_config(args.name)
    used_keyring = store_telegram_creds(args.name, args.token, args.chat_id)
    if used_keyring:
        cfg["telegram_bot_token"] = ""
        cfg["telegram_chat_id"] = ""
        print("Telegram credentials stored in Windows Credential Manager (keyring).")
    else:
        cfg["telegram_bot_token"] = args.token
        cfg["telegram_chat_id"] = args.chat_id
        print("Telegram settings saved in config file (install 'keyring' for secure storage).")
    save_config(folder, cfg)
    print("Keep your bot token private.")
    return 0


def cmd_telegram_clear(args) -> int:
    folder, cfg = load_config(args.name)
    delete_telegram_creds(args.name)
    cfg["telegram_bot_token"] = ""
    cfg["telegram_chat_id"] = ""
    save_config(folder, cfg)
    print(f"Telegram credentials cleared for '{args.name}'.")
    return 0


# ── startup ───────────────────────────────────────────────────────────────────

def _startup_file(name: str) -> Path:
    appdata = Path(os.environ.get("APPDATA", Path.home()))
    return (
        appdata / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
        / f"Watchman-{name}.cmd"
    )


def cmd_startup(args) -> int:
    folder, cfg = load_config(args.name)
    target = _startup_file(args.name)

    if args.action == "status":
        enabled = target.exists() and cfg.get("startup_enabled", False)
        print(f"Startup for '{args.name}': {'enabled' if enabled else 'disabled'}")
        if enabled:
            print(f"Entry: {target}")
        return 0

    if args.action == "enable":
        if not cfg.get("protected_paths"):
            print("Add at least one protected folder before enabling startup.")
            return 2
        target.parent.mkdir(parents=True, exist_ok=True)
        python = sys.executable
        target.write_text(
            f"@echo off\r\n"
            f" title Watchman - {args.name}\r\n"
            f'"{python}" -m watchman start {args.name}\r\n',
            encoding="utf-8",
        )
        cfg["startup_enabled"] = True
        save_config(folder, cfg)
        print(f"Startup enabled for '{args.name}' at user logon.")
        print(f"Entry: {target}")
        print(f"Remove with: watchman startup disable {args.name}")
        return 0

    # disable
    if target.exists():
        target.unlink()
    cfg["startup_enabled"] = False
    save_config(folder, cfg)
    print(f"Startup disabled for '{args.name}'.")
    return 0


# ── parser ────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="watchman",
        description="Watchman - local Windows file integrity monitor",
    )
    sub = p.add_subparsers(dest="command", required=True)

    # init
    q = sub.add_parser("init", help="Create a deployment without starting monitoring")
    q.add_argument("name")
    q.set_defaults(func=cmd_init)

    # list
    q = sub.add_parser("list", help="List deployments (shows [RUNNING] if background daemon active)")
    q.set_defaults(func=cmd_list)

    # start
    q = sub.add_parser("start", help="Start monitoring (foreground by default)")
    q.add_argument("name")
    q.add_argument(
        "--background", "-b",
        action="store_true",
        help="Detach and run as a background daemon; use 'watchman stop <name>' to terminate",
    )
    q.set_defaults(func=cmd_start)

    # stop
    q = sub.add_parser("stop", help="Stop a background daemon started with --background")
    q.add_argument("name")
    q.set_defaults(func=cmd_stop)

    # status
    q = sub.add_parser("status", help="Show whether a background daemon is running")
    q.add_argument("name")
    q.set_defaults(func=cmd_status)

    # logs
    q = sub.add_parser("logs", help="Show recorded events")
    q.add_argument("name")
    q.add_argument("--limit", type=int, default=50)
    q.set_defaults(func=cmd_logs)

    # watch
    watch = sub.add_parser("watch", help="Manage protected paths").add_subparsers(
        dest="watch_action", required=True
    )
    q = watch.add_parser("add", help="Add a protected directory")
    q.add_argument("name")
    q.add_argument("path")
    q.add_argument(
        "--exclude", metavar="PATTERN", action="append", default=[],
        help="Glob pattern to exclude (repeatable, e.g. --exclude '*.tmp')",
    )
    q.set_defaults(func=cmd_add)

    q = watch.add_parser("remove", help="Remove a protected directory")
    q.add_argument("name")
    q.add_argument("path")
    q.set_defaults(func=cmd_remove)

    q = watch.add_parser("list", help="List protected directories")
    q.add_argument("name")
    q.set_defaults(func=cmd_paths)

    # scan / verify
    q = sub.add_parser("scan", help="Snapshot SHA-256 hashes of all protected files (baseline)")
    q.add_argument("name")
    q.set_defaults(func=cmd_scan)

    q = sub.add_parser(
        "verify",
        help="Compare current file state to baseline; exits 1 if changes detected",
    )
    q.add_argument("name")
    q.set_defaults(func=cmd_verify)

    # export
    q = sub.add_parser("export", help="Export the event log to JSON or CSV")
    q.add_argument("name")
    q.add_argument("--format", choices=["json", "csv"], default="json")
    q.add_argument("--output", metavar="FILE", help="Write to FILE instead of stdout")
    q.set_defaults(func=cmd_export)

    # clear
    q = sub.add_parser("clear", help="Delete all recorded events for a deployment")
    q.add_argument("name")
    q.add_argument("--yes", action="store_true", help="Skip interactive confirmation")
    q.set_defaults(func=cmd_clear)

    # telegram
    q = sub.add_parser("telegram", help="Configure Telegram notifications")
    q.add_argument("name")
    q.add_argument("--token", required=True)
    q.add_argument("--chat-id", required=True)
    q.set_defaults(func=cmd_telegram)

    q = sub.add_parser("telegram-clear", help="Remove stored Telegram credentials")
    q.add_argument("name")
    q.set_defaults(func=cmd_telegram_clear)

    # startup
    q = sub.add_parser("startup", help="Manage opt-in Windows logon startup")
    q.add_argument("action", choices=["enable", "disable", "status"])
    q.add_argument("name")
    q.set_defaults(func=cmd_startup)

    return p


# ── entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(errors="replace")
            sys.stderr.reconfigure(errors="replace")
        except Exception:
            pass
    try:
        args = build_parser().parse_args()
        if getattr(args, "limit", 1) < 1:
            print("--limit must be >= 1")
            raise SystemExit(2)
        raise SystemExit(args.func(args) or 0)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(2)


if __name__ == "__main__":
    main()
