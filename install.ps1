# =============================================================================
#  Watchman — remote installer
#  https://github.com/YOUR_USERNAME/watchman
#
#  USAGE (run in PowerShell as your normal user account):
#
#    irm https://raw.githubusercontent.com/YOUR_USERNAME/watchman/main/install.ps1 | iex
#
#  WHAT THIS SCRIPT DOES:
#    1. Checks for Python 3.10+
#    2. Downloads the latest Watchman source from GitHub
#    3. Installs the 'watchman' CLI for the current user via pip
#    4. Cleans up temporary files
#
#  WHAT THIS SCRIPT DOES NOT DO:
#    - It does NOT create any deployments
#    - It does NOT start monitoring any folders
#    - It does NOT enable or install any background service or startup entry
#    - It does NOT require administrator privileges
#
#  Review this script at the URL above before running it.
#  Never pipe an unreviewed script from the internet into your shell.
# =============================================================================

$ErrorActionPreference = 'Stop'
$ProgressPreference    = 'SilentlyContinue'

# ── Configuration (update these to match your GitHub repo) ───────────────────
$GITHUB_OWNER   = 'YOUR_USERNAME'
$GITHUB_REPO    = 'watchman'
$GITHUB_BRANCH  = 'main'
$INSTALL_DIR    = Join-Path $env:LOCALAPPDATA 'Watchman\app'
# ─────────────────────────────────────────────────────────────────────────────

$ZIP_URL = "https://github.com/$GITHUB_OWNER/$GITHUB_REPO/archive/refs/heads/$GITHUB_BRANCH.zip"

# Banner
Write-Host ''
Write-Host '  ██╗    ██╗ █████╗ ████████╗ ██████╗██╗  ██╗███╗   ███╗ █████╗ ███╗   ██╗' -ForegroundColor Cyan
Write-Host '  ██║    ██║██╔══██╗╚══██╔══╝██╔════╝██║  ██║████╗ ████║██╔══██╗████╗  ██║' -ForegroundColor Cyan
Write-Host '  ██║ █╗ ██║███████║   ██║   ██║     ███████║██╔████╔██║███████║██╔██╗ ██║' -ForegroundColor Cyan
Write-Host '  ██║███╗██║██╔══██║   ██║   ██║     ██╔══██║██║╚██╔╝██║██╔══██║██║╚██╗██║' -ForegroundColor Cyan
Write-Host '  ╚███╔███╔╝██║  ██║   ██║   ╚██████╗██║  ██║██║ ╚═╝ ██║██║  ██║██║ ╚████║' -ForegroundColor Cyan
Write-Host '   ╚══╝╚══╝ ╚═╝  ╚═╝   ╚═╝    ╚═════╝╚═╝  ╚═╝╚═╝     ╚═╝╚═╝  ╚═╝╚═╝  ╚═══╝' -ForegroundColor Cyan
Write-Host ''
Write-Host '  Local file integrity monitor for Windows' -ForegroundColor DarkGray
Write-Host '  ─────────────────────────────────────────────────────────────────' -ForegroundColor DarkGray
Write-Host ''
Write-Host '  This installer will:' -ForegroundColor White
Write-Host '    • Install the watchman CLI for your user account'
Write-Host '    • NOT start monitoring or create any deployment'
Write-Host '    • NOT require administrator privileges'
Write-Host ''

# ── Step 1: Locate Python 3.10+ ──────────────────────────────────────────────
Write-Host '  [1/4] Checking Python...' -ForegroundColor Yellow

$PythonCmd = $null
$PythonVersion = $null

foreach ($candidate in @('py', 'python3', 'python')) {
    try {
        $raw = & $candidate --version 2>&1
        if ($raw -match 'Python 3\.(\d+)\.(\d+)') {
            $minor = [int]$Matches[1]
            if ($minor -ge 10) {
                $PythonCmd     = $candidate
                $PythonVersion = $raw.ToString().Trim()
                break
            }
        }
    } catch { }
}

if (-not $PythonCmd) {
    Write-Host ''
    Write-Host '  ✗ Python 3.10 or newer is required.' -ForegroundColor Red
    Write-Host '    Download from: https://www.python.org/downloads/' -ForegroundColor Red
    Write-Host '    Make sure to check "Add Python to PATH" during setup.' -ForegroundColor Red
    Write-Host ''
    exit 1
}

Write-Host "  ✓ Found $PythonVersion" -ForegroundColor Green

# ── Step 2: Download source archive ──────────────────────────────────────────
Write-Host ''
Write-Host '  [2/4] Downloading Watchman...' -ForegroundColor Yellow

$TempZip = Join-Path $env:TEMP 'watchman-install.zip'
$TempDir = Join-Path $env:TEMP 'watchman-install'

try {
    Invoke-WebRequest -Uri $ZIP_URL -OutFile $TempZip -UseBasicParsing
} catch {
    Write-Host ''
    Write-Host "  ✗ Download failed: $_" -ForegroundColor Red
    Write-Host "    URL: $ZIP_URL" -ForegroundColor DarkGray
    Write-Host '    Check your internet connection and that the repository is public.' -ForegroundColor DarkGray
    Write-Host ''
    exit 1
}

Write-Host '  ✓ Downloaded' -ForegroundColor Green

# ── Step 3: Extract + copy to install location ────────────────────────────────
Write-Host ''
Write-Host '  [3/4] Installing...' -ForegroundColor Yellow

if (Test-Path $TempDir) { Remove-Item $TempDir -Recurse -Force }
Expand-Archive -Path $TempZip -DestinationPath $TempDir -Force
Remove-Item $TempZip -Force

# GitHub zips extract to <repo>-<branch>/
$Extracted = Get-ChildItem $TempDir -Directory | Select-Object -First 1
if (-not $Extracted) {
    Write-Host '  ✗ Archive extraction failed — no source folder found.' -ForegroundColor Red
    exit 1
}

New-Item -ItemType Directory -Force -Path $INSTALL_DIR | Out-Null
Copy-Item -Path (Join-Path $Extracted.FullName '*') -Destination $INSTALL_DIR -Recurse -Force

# pip install --user (no admin required)
$PipArgs = @('-m', 'pip', 'install', '--user', '--quiet', $INSTALL_DIR)
if ($PythonCmd -eq 'py') {
    & py -3 @PipArgs
} else {
    & $PythonCmd @PipArgs
}

if ($LASTEXITCODE -ne 0) {
    Write-Host '  ✗ pip install failed. See errors above.' -ForegroundColor Red
    exit 1
}

# Optional: install secure credential backend
$answer = Read-Host '  Install Windows Credential Manager support for Telegram tokens? [y/N]'
if ($answer -match '^[Yy]') {
    $SecureArgs = @('-m', 'pip', 'install', '--user', '--quiet', 'keyring>=24.0.0')
    if ($PythonCmd -eq 'py') { & py -3 @SecureArgs } else { & $PythonCmd @SecureArgs }
    Write-Host '  ✓ Keyring installed — Telegram tokens will be stored securely.' -ForegroundColor Green
}

# ── Step 4: Cleanup ───────────────────────────────────────────────────────────
Remove-Item $TempDir -Recurse -Force -ErrorAction SilentlyContinue

Write-Host ''
Write-Host '  ─────────────────────────────────────────────────────────────────' -ForegroundColor DarkGray
Write-Host '  ✓ Watchman installed successfully!' -ForegroundColor Green
Write-Host ''
Write-Host '  Quick start:' -ForegroundColor Cyan
Write-Host ''
Write-Host '    # Create a deployment'
Write-Host '    watchman init mywatch'
Write-Host ''
Write-Host '    # Add a folder to protect'
Write-Host '    watchman watch add mywatch "C:\Users\You\Documents"'
Write-Host ''
Write-Host '    # Start monitoring in the background'
Write-Host '    watchman start mywatch --background'
Write-Host ''
Write-Host '    # View events'
Write-Host '    watchman logs mywatch'
Write-Host ''
Write-Host '    # Stop the daemon'
Write-Host '    watchman stop mywatch'
Write-Host ''
Write-Host '  Run "watchman --help" for all commands.' -ForegroundColor DarkGray
Write-Host ''

# Remind user about PATH if watchman isn't immediately found
$WatchmanPath = (Get-Command watchman -ErrorAction SilentlyContinue)
if (-not $WatchmanPath) {
    Write-Host '  NOTE: "watchman" may not be on your PATH yet.' -ForegroundColor Yellow
    Write-Host '  Restart PowerShell, or add the pip user scripts folder to PATH:' -ForegroundColor Yellow
    $ScriptsDir = & $PythonCmd -c "import sysconfig; print(sysconfig.get_path('scripts', 'nt_user'))" 2>$null
    if ($ScriptsDir) {
        Write-Host "    $ScriptsDir" -ForegroundColor DarkGray
    }
    Write-Host ''
}
