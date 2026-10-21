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

    # ── Helper: Environment PATH Registration ────────────────────────────────
    function Add-PathToUserEnv {
        param([string]$DirPath)
        if (-not $DirPath) { return }
        $cleanDir = $DirPath.Trim().TrimEnd('\', '/')
        if (-not $cleanDir) { return }

        # Ensure directory exists
        if (-not (Test-Path $cleanDir)) {
            New-Item -ItemType Directory -Path $cleanDir -Force -ErrorAction SilentlyContinue | Out-Null
        }

        # 1. Update current PowerShell session PATH
        $sessionPaths = ($env:PATH -split ';') | Where-Object { $_ -ne '' }
        $alreadyInSession = $false
        foreach ($p in $sessionPaths) {
            if ($p.TrimEnd('\', '/') -ieq $cleanDir) {
                $alreadyInSession = $true
                break
            }
        }
        if (-not $alreadyInSession) {
            $env:PATH = "$cleanDir;$env:PATH"
        }

        # 2. Update persistent User PATH in Windows Registry
        $userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
        $userPaths = if ($userPath) { ($userPath -split ';') | Where-Object { $_ -ne '' } } else { @() }
        $alreadyInUser = $false
        foreach ($p in $userPaths) {
            if ($p.TrimEnd('\', '/') -ieq $cleanDir) {
                $alreadyInUser = $true
                break
            }
        }
        if (-not $alreadyInUser) {
            $newUserPath = ($userPaths + $cleanDir) -join ';'
            [Environment]::SetEnvironmentVariable('Path', $newUserPath, 'User')
        }
    }

    # ── Helper: Find Python 3.10+ Executable ──────────────────────────────────
    function Find-PythonRuntime {
        $candidates = [System.Collections.Generic.List[string]]::new()
        foreach ($c in @('py', 'python3', 'python')) {
            $candidates.Add($c)
        }

        # Check common local app install directories
        $programsPython = Join-Path $env:LOCALAPPDATA 'Programs\Python'
        if (Test-Path $programsPython) {
            Get-ChildItem -Path $programsPython -Filter 'python.exe' -Recurse -Depth 2 -ErrorAction SilentlyContinue |
                ForEach-Object { $candidates.Add($_.FullName) }
        }

        # Check Microsoft Store Python packages
        $storePython = Join-Path $env:LOCALAPPDATA 'Microsoft\WindowsApps'
        if (Test-Path $storePython) {
            Get-ChildItem -Path $storePython -Filter 'python3*.exe' -ErrorAction SilentlyContinue |
                ForEach-Object { $candidates.Add($_.FullName) }
        }

        foreach ($candidate in $candidates) {
            try {
                $raw = & $candidate --version 2>&1
                if ($raw -match 'Python 3\.(\d+)\.(\d+)') {
                    $minor = [int]$Matches[1]
                    if ($minor -ge 10) {
                        return @{
                            Cmd     = $candidate
                            Version = $raw.ToString().Trim()
                        }
                    }
                }
            } catch { }
        }

        return @{
            Cmd     = $null
            Version = $null
        }
    }

    # ── Step 1: Check Python 3.10+ (Auto-Install if Missing) ──────────────────
    Write-Host '  [1/4] Checking Python...' -ForegroundColor Yellow

    $pyInfo = Find-PythonRuntime
    $PythonCmd     = $pyInfo.Cmd
    $PythonVersion = $pyInfo.Version

    if (-not $PythonCmd) {
        Write-Host '  Python 3.10 or newer was not detected on your system.' -ForegroundColor Yellow
        Write-Host '  Attempting automatic download & installation...' -ForegroundColor Cyan

        $autoInstalled = $false

        # Strategy 1: winget (standard Windows package manager, user scope)
        if (Get-Command winget -ErrorAction SilentlyContinue) {
            Write-Host '  Installing Python 3.12 via winget...' -ForegroundColor Cyan
            try {
                $proc = Start-Process -FilePath 'winget' `
                    -ArgumentList 'install --id Python.Python.3.12 -e --scope user --silent --accept-source-agreements --accept-package-agreements' `
                    -NoNewWindow -Wait -PassThru
                if ($proc.ExitCode -eq 0) {
                    $autoInstalled = $true
                }
            } catch { }
        }

        # Strategy 2: Download official installer from python.org (silent user-level install)
        if (-not $autoInstalled) {
            Write-Host '  Downloading official Python 3.12 installer from python.org...' -ForegroundColor Cyan
            $arch = if ([Environment]::Is64BitOperatingSystem) {
                if ($env:PROCESSOR_ARCHITECTURE -eq 'ARM64') { 'arm64' } else { 'amd64' }
            } else { 'win32' }

            $pyVer = '3.12.8'
            $installerFile = if ($arch -eq 'arm64') {
                "python-$pyVer-arm64.exe"
            } elseif ($arch -eq 'amd64') {
                "python-$pyVer-amd64.exe"
            } else {
                "python-$pyVer.exe"
            }
            $installerUrl = "https://www.python.org/ftp/python/$pyVer/$installerFile"
            $tempInstaller = Join-Path $env:TEMP $installerFile

            try {
                Invoke-WebRequest -Uri $installerUrl -OutFile $tempInstaller -UseBasicParsing
                Write-Host '  Running silent user installer (no administrator privileges needed)...' -ForegroundColor Cyan
                # Arguments:
                # InstallAllUsers=0 : Installs to %LOCALAPPDATA%\Programs\Python (no admin needed)
                # PrependPath=1    : Adds python and scripts to user PATH
                # Include_pip=1    : Ensures pip is installed
                # Include_test=0   : Skips test suite for fast install
                # SimpleInstall=1  : Standard default configuration
                $proc = Start-Process -FilePath $tempInstaller `
                    -ArgumentList '/quiet InstallAllUsers=0 PrependPath=1 Include_pip=1 Include_test=0 SimpleInstall=1' `
                    -Wait -PassThru
                if ($proc.ExitCode -eq 0) {
                    $autoInstalled = $true
                }
            } catch {
                Write-Host "  Auto-download error: $_" -ForegroundColor DarkGray
            } finally {
                if (Test-Path $tempInstaller) {
                    Remove-Item $tempInstaller -Force -ErrorAction SilentlyContinue
                }
            }
        }

        # Refresh session PATH from registry after installation
        $uPath = [Environment]::GetEnvironmentVariable('Path', 'User')
        $mPath = [Environment]::GetEnvironmentVariable('Path', 'Machine')
        $env:PATH = "$uPath;$mPath"

        # Re-check for Python runtime
        $pyInfo = Find-PythonRuntime
        $PythonCmd     = $pyInfo.Cmd
        $PythonVersion = $pyInfo.Version

        if (-not $PythonCmd) {
            Write-Host ''
            Write-Host '  [ERROR] Python 3.10 or newer is required and automatic installation could not be completed.' -ForegroundColor Red
            Write-Host '  Please download and install Python manually from: https://www.python.org/downloads/' -ForegroundColor Red
            Write-Host '  Ensure "Add Python to PATH" is checked during setup.' -ForegroundColor Red
            Write-Host ''
            return
        }

        Write-Host "  [OK] Successfully installed $PythonVersion" -ForegroundColor Green
    } else {
        Write-Host "  [OK] Found $PythonVersion" -ForegroundColor Green
    }

    # ── Step 2: Download or copy source ───────────────────────────────────────
    Write-Host ''
    Write-Host "  [2/4] Downloading Watchman from $GITHUB_OWNER/$GITHUB_REPO..." -ForegroundColor Yellow

    $TempZip = Join-Path $env:TEMP 'watchman-install.zip'
    $TempDir = Join-Path $env:TEMP 'watchman-install'

    # Check if installer is running from a local repository clone
    $LocalSource = if ($PSScriptRoot -and (Test-Path (Join-Path $PSScriptRoot 'pyproject.toml'))) { $PSScriptRoot } else { $null }

    if ($LocalSource) {
        Write-Host "  Using local repository files from $LocalSource" -ForegroundColor DarkGray
        New-Item -ItemType Directory -Force -Path $INSTALL_DIR | Out-Null
        Copy-Item -Path (Join-Path $LocalSource '*') -Destination $INSTALL_DIR -Recurse -Force
        Write-Host '  [OK] Source files copied' -ForegroundColor Green
    } else {
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

        # Extract archive
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
        } catch {
            Write-Host "  [ERROR] Archive extraction failed: $_" -ForegroundColor Red
            return
        } finally {
            Remove-Item $TempDir -Recurse -Force -ErrorAction SilentlyContinue
        }
    }

    # ── Step 3: Install Package & Configure PATH ──────────────────────────────
    Write-Host ''
    Write-Host '  [3/4] Installing Watchman...' -ForegroundColor Yellow

    try {
        # Discover and pre-configure Python User Scripts directories on PATH
        $ScriptsDirs = @()
        foreach ($pyCode in @(
            "import sysconfig; print(sysconfig.get_path('scripts', 'nt_user') or '')",
            "import sysconfig; print(sysconfig.get_path('scripts') or '')"
        )) {
            try {
                $dirRaw = if ($PythonCmd -eq 'py') {
                    (& py -3 -c $pyCode 2>$null)
                } else {
                    (& $PythonCmd -c $pyCode 2>$null)
                }
                if ($dirRaw) {
                    $d = $dirRaw.ToString().Trim()
                    if ($d -and ($ScriptsDirs -notcontains $d)) {
                        $ScriptsDirs += $d
                        Add-PathToUserEnv -DirPath $d
                    }
                }
            } catch { }
        }

        # pip install --user (no admin required)
        # --no-warn-script-location: suppresses PATH warnings during install
        # --default-timeout=60: avoids ReadTimeoutError on slow connections
        $PipArgs = @(
            '-m', 'pip', 'install',
            '--user',
            '--quiet',
            '--no-warn-script-location',
            '--default-timeout=60',
            $INSTALL_DIR
        )

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
    }

    # Ensure the directory containing the installed watchman.exe is registered in PATH
    $WatchmanExePath = $null
    $WatchmanCmd = (Get-Command watchman -ErrorAction SilentlyContinue)
    if ($WatchmanCmd) {
        $WatchmanExePath = $WatchmanCmd.Source
    }

    if (-not $WatchmanExePath) {
        # Search candidate scripts directories
        foreach ($sd in $ScriptsDirs) {
            $candidate = Join-Path $sd 'watchman.exe'
            if (Test-Path $candidate) {
                $WatchmanExePath = $candidate
                Add-PathToUserEnv -DirPath $sd
                break
            }
        }
    }

    if (-not $WatchmanExePath) {
        # Search common user installation directories
        $globs = @(
            (Join-Path $env:APPDATA 'Python\Python*\Scripts\watchman.exe'),
            (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python*\Scripts\watchman.exe'),
            (Join-Path $env:LOCALAPPDATA 'Packages\PythonSoftwareFoundation.Python.*\LocalCache\local-packages\Python*\Scripts\watchman.exe')
        )
        foreach ($g in $globs) {
            $matched = Get-Item -Path $g -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($matched) {
                $WatchmanExePath = $matched.FullName
                Add-PathToUserEnv -DirPath $matched.DirectoryName
                break
            }
        }
    }

    Write-Host '  [OK] Core package installed.' -ForegroundColor Green
    if ($WatchmanExePath) {
        Write-Host "  [OK] Registered '$([System.IO.Path]::GetDirectoryName($WatchmanExePath))' onto User PATH." -ForegroundColor Green
    }

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
    if ($WatchmanCmd) {
        Write-Host '  [OK] "watchman" CLI is active and ready to use.' -ForegroundColor Green
        Write-Host ''
    } else {
        Write-Host '  NOTE: "watchman" command was added to your persistent User PATH.' -ForegroundColor Yellow
        Write-Host '  If not recognized in this specific terminal window, please reopen PowerShell or run:' -ForegroundColor Yellow
        Write-Host "    $PythonCmd -m watchman --help" -ForegroundColor Cyan
        Write-Host ''
    }
}
