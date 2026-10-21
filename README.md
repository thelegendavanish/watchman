# Watchman

A locally installed, user-controlled Windows file integrity monitor.
Watchman watches only explicitly configured directories, records every filesystem
event to a local SQLite database, computes SHA-256 hashes for tamper detection,
and optionally delivers real-time Telegram alerts.

> No administrator privileges required. No hidden services. Nothing runs unless
> you explicitly ask it to.

## Requirements

- Windows 10/11
- Python 3.10 or newer (automatically installed if missing, or manual download from `python.org/downloads`)
- Network access only if you enable Telegram notifications

---

## Install

### One-liner (hosted installer)

Open **PowerShell** and run:

```powershell
irm https://raw.githubusercontent.com/thelegendavanish/watchman/main/install.ps1 | iex
```

> **Before running any `irm | iex` command**, review the script at the URL above.
> This installer downloads source from GitHub, runs `pip install --user`, and
> does **nothing else** — no services, no startup entries, no admin access.

### Manual install (from downloaded folder)

```powershell
python -m pip install --user .

# Optional: secure Windows Credential Manager storage for Telegram tokens
python -m pip install --user ".[secure]"
```

---

## Uninstall

To completely remove Watchman, all background daemons, startup entries, and local databases:

### One-liner:
```powershell
irm https://raw.githubusercontent.com/thelegendavanish/watchman/main/uninstall.ps1 | iex
```

### Or manually via PowerShell:
```powershell
# 1. Uninstall the CLI package
python -m pip uninstall -y watchman

# 2. Remove configuration and database directories
Remove-Item -Recurse -Force "$env:LOCALAPPDATA\Watchman" -ErrorAction SilentlyContinue

# 3. Remove any startup entries
Remove-Item -Force "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\Watchman-*.cmd" -ErrorAction SilentlyContinue
```

---

## Quick start

```powershell
# 1. Create a named deployment
watchman init mywatch

# 2. Add folders to protect
watchman watch add mywatch "C:\Users\You\Documents"
watchman watch add mywatch "D:\Projects" --exclude "*.tmp" --exclude "~$*"

# 3. Optional: Telegram alerts
watchman telegram mywatch --token "BOT_TOKEN" --chat-id "CHAT_ID"

# 4a. Foreground monitoring (Ctrl+C to stop)
watchman start mywatch

# 4b. Background daemon
watchman start mywatch --background
watchman status mywatch          # check running state + PID
watchman stop  mywatch           # stop the daemon
```

---

## Background daemon mode

```powershell
watchman start  mywatch --background   # detach; returns prompt immediately
watchman status mywatch                # → RUNNING (PID 12345), log path
watchman stop   mywatch                # graceful termination via Windows API
watchman list                          # shows [RUNNING] badge when active
```

Logs are written to:
```
%LOCALAPPDATA%\Watchman\deployments\<name>\monitor.log
```

---

## Baseline integrity scan

```powershell
# Snapshot SHA-256 of every file under protected paths
watchman scan mywatch

# Later — diff live state against the snapshot
watchman verify mywatch     # exits 0 if clean, 1 if changes found
```

---

## Event log

```powershell
watchman logs mywatch --limit 100

# Export
watchman export mywatch --format json --output events.json
watchman export mywatch --format csv  --output events.csv

# Clear (interactive confirmation)
watchman clear mywatch
watchman clear mywatch --yes    # non-interactive
```

---

## Multiple deployments

```powershell
watchman init work
watchman watch add work "D:\Work"
watchman init personal
watchman watch add personal "$HOME\Documents"
watchman list
```

Each deployment is fully independent, stored under:
```
%LOCALAPPDATA%\Watchman\deployments\<name>\
    config.json       ← protected paths, exclude patterns, startup flag
    events.sqlite3    ← tamper-evident event log (chain-hashed)
    monitor.pid       ← PID of background daemon (when running)
    monitor.log       ← stdout of background daemon
```

---

## Windows logon startup (opt-in)

```powershell
watchman startup enable  mywatch
watchman startup status  mywatch
watchman startup disable mywatch
```

Enabling startup creates a **visible** `.cmd` entry in the user's Startup folder.
It opens a visible console window — no hidden persistence.

---

## All commands

| Command | Description |
|---------|-------------|
| `watchman init NAME` | Create a deployment |
| `watchman list` | List all deployments (`[RUNNING]` if daemon active) |
| `watchman start NAME [--background]` | Start foreground or background daemon |
| `watchman stop NAME` | Stop a background daemon |
| `watchman status NAME` | Show PID and log path |
| `watchman watch add NAME PATH [--exclude PAT]` | Add a protected directory |
| `watchman watch remove NAME PATH` | Remove a directory |
| `watchman watch list NAME` | List directories and exclude patterns |
| `watchman logs NAME [--limit N]` | Show recent events |
| `watchman scan NAME` | Take a baseline hash snapshot |
| `watchman verify NAME` | Compare live files to baseline |
| `watchman export NAME [--format json\|csv] [--output FILE]` | Export event log |
| `watchman clear NAME [--yes]` | Delete all recorded events |
| `watchman telegram NAME --token T --chat-id C` | Configure Telegram |
| `watchman telegram-clear NAME` | Remove Telegram credentials |
| `watchman startup enable\|disable\|status NAME` | Manage logon startup |

---

## Hosting on GitHub (to enable `irm | iex`)

1. Push this repository to GitHub (public or private with a PAT).
2. Edit [`install.ps1`](install.ps1): replace `YOUR_USERNAME` with your GitHub username.
3. Users can then install with:
   ```powershell
   irm https://raw.githubusercontent.com/YOUR_USERNAME/watchman/main/install.ps1 | iex
   ```
4. To release versioned builds, use **GitHub Releases** and update `$GITHUB_BRANCH`
   in `install.ps1` to a tag (e.g. `v0.2.0`).

---

## Security notes

- **Telegram tokens** are stored in **Windows Credential Manager** when the
  optional `keyring` package is installed. Without it, they fall back to
  `config.json` — restrict access to your Windows user account.
- The event log uses **chain hashing** (`prev_event_hash`): each row's hash is
  computed over itself and the previous row, making sequential deletions harder
  to hide undetected.
- SQLite logs are local and can still be altered by a privileged user. For
  stronger evidence integrity, export signed checkpoints to a separate system.
- `watchdog` can miss events during OS notification backlog. Use
  `watchman scan` + `watchman verify` for periodic integrity checks.
- Monitoring only covers directories the current user can access.
- Test with a temporary folder before protecting important documents.

---

## Development & testing

```powershell
python -m pip install --user -e ".[dev]"
python -m pytest
```
