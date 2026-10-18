# =============================================================================
#  Watchman - remote installer
#  https://github.com/thelegendavanish/watchman
#
#  USAGE (run in PowerShell as your normal user account):
#
#    irm https://raw.githubusercontent.com/thelegendavanish/watchman/main/install.ps1 | iex
# =============================================================================

& {
    $ErrorActionPreference = 'Stop'
    $ProgressPreference    = 'SilentlyContinue'

    $GITHUB_OWNER   = 'thelegendavanish'
    $GITHUB_REPO    = 'watchman'
    $GITHUB_BRANCH  = 'main'
    $INSTALL_DIR    = Join-Path $env:LOCALAPPDATA 'Watchman\app'
    $ZIP_URL        = "https://github.com/$GITHUB_OWNER/$GITHUB_REPO/archive/refs/heads/$GITHUB_BRANCH.zip"

    Write-Host ''
    Write-Host '  ==================================================' -ForegroundColor Cyan
    Write-Host '               WATCHMAN INSTALLER                  ' -ForegroundColor Cyan
    Write-Host '    Local File Integrity Monitor for Windows       ' -ForegroundColor DarkGray
    Write-Host '  ==================================================' -ForegroundColor Cyan
    Write-Host ''
    Write-Host '  This installer will:' -ForegroundColor White
    Write-Host '    * Install the watchman CLI for your current user'
    Write-Host '    * NOT require Administrator privileges'
    Write-Host '    * NOT start monitoring or alter startup entries'
    Write-Host ''

    # ── Step 1: Check Python 3.10+ ───────────────────────────────────────────
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
        Write-Host '  [ERROR] Python 3.10 or newer is required.' -ForegroundColor Red
        Write-Host '  Download from: https://www.python.org/downloads/' -ForegroundColor Red
        Write-Host '  Ensure "Add Python to PATH" is checked during setup.' -ForegroundColor Red
        Write-Host ''
        return
    }

    Write-Host "  [OK] Found $PythonVersion" -ForegroundColor Green

    # ── Step 2: Download source archive ───────────────────────────────────────
    Write-Host ''
    Write-Host "  [2/4] Downloading Watchman from $GITHUB_OWNER/$GITHUB_REPO..." -ForegroundColor Yellow

    $TempZip = Join-Path $env:TEMP 'watchman-install.zip'
    $TempDir = Join-Path $env:TEMP 'watchman-install'

    try {
        Invoke-WebRequest -Uri $ZIP_URL -OutFile $TempZip -UseBasicParsing
    } catch {
        Write-Host ''
        Write-Host "  [ERROR] Download failed: $_" -ForegroundColor Red
        Write-Host "  URL: $ZIP_URL" -ForegroundColor DarkGray
        Write-Host '  Please check your internet connection or verify the repository is public.' -ForegroundColor DarkGray
        Write-Host ''
        return
    }

    Write-Host '  [OK] Download complete' -ForegroundColor Green

    # ── Step 3: Extract + copy to install location ─────────────────────────────
    Write-Host ''
    Write-Host '  [3/4] Installing Watchman...' -ForegroundColor Yellow

    try {
        if (Test-Path $TempDir) { Remove-Item $TempDir -Recurse -Force -ErrorAction SilentlyContinue }
        Expand-Archive -Path $TempZip -DestinationPath $TempDir -Force
        Remove-Item $TempZip -Force -ErrorAction SilentlyContinue

        $Extracted = Get-ChildItem $TempDir -Directory | Select-Object -First 1
        if (-not $Extracted) {
            Write-Host '  [ERROR] Archive extraction failed - source folder not found.' -ForegroundColor Red
            return
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
            Write-Host '  [ERROR] pip install failed.' -ForegroundColor Red
            return
        }
    } catch {
        Write-Host "  [ERROR] Installation step failed: $_" -ForegroundColor Red
        return
    } finally {
        Remove-Item $TempDir -Recurse -Force -ErrorAction SilentlyContinue
    }

    Write-Host '  [OK] Core package installed.' -ForegroundColor Green

    # ── Step 4: Verification & PATH check ─────────────────────────────────────
    Write-Host ''
    Write-Host '  --------------------------------------------------' -ForegroundColor DarkGray
    Write-Host '  [OK] Watchman installed successfully!' -ForegroundColor Green
    Write-Host '  --------------------------------------------------' -ForegroundColor DarkGray
    Write-Host ''
    Write-Host '  Quick Start:' -ForegroundColor Cyan
    Write-Host ''
    Write-Host '    # 1. Create a deployment'
    Write-Host '    watchman init mywatch'
    Write-Host ''
    Write-Host '    # 2. Add folders to protect'
    Write-Host '    watchman watch add mywatch "$HOME\Documents"'
    Write-Host ''
    Write-Host '    # 3. Take a baseline integrity snapshot'
    Write-Host '    watchman scan mywatch'
    Write-Host ''
    Write-Host '    # 4. Start background monitoring'
    Write-Host '    watchman start mywatch --background'
    Write-Host ''
    Write-Host '    # 5. Check daemon status and logs'
    Write-Host '    watchman status mywatch'
    Write-Host '    watchman logs mywatch'
    Write-Host ''
    Write-Host '    # 6. Stop the background daemon'
    Write-Host '    watchman stop mywatch'
    Write-Host ''
    Write-Host '  Run "watchman --help" for all available commands.' -ForegroundColor DarkGray
    Write-Host ''

    $WatchmanCmd = (Get-Command watchman -ErrorAction SilentlyContinue)
    if (-not $WatchmanCmd) {
        Write-Host '  NOTE: "watchman" command is not yet in your current session PATH.' -ForegroundColor Yellow
        Write-Host '  Close and reopen PowerShell, or run Watchman via Python:' -ForegroundColor Yellow
        Write-Host "    $PythonCmd -m watchman --help" -ForegroundColor Cyan
        Write-Host ''
    }
}
