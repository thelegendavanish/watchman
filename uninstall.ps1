# =============================================================================
#  Watchman - uninstaller
#  https://github.com/thelegendavanish/watchman
#
#  USAGE:
#    irm https://raw.githubusercontent.com/thelegendavanish/watchman/main/uninstall.ps1 | iex
# =============================================================================

& {
    $ErrorActionPreference = 'SilentlyContinue'

    Write-Host ''
    Write-Host '  ==================================================' -ForegroundColor Yellow
    Write-Host '               WATCHMAN UNINSTALLER                ' -ForegroundColor Yellow
    Write-Host '  ==================================================' -ForegroundColor Yellow
    Write-Host ''

    # 1. Stop any running background monitors
    Write-Host '  [1/5] Stopping any running background daemons...' -ForegroundColor Yellow
    $DeploymentsDir = Join-Path $env:LOCALAPPDATA 'Watchman\deployments'
    if (Test-Path $DeploymentsDir) {
        Get-ChildItem -Path $DeploymentsDir -Directory | ForEach-Object {
            $pidFile = Join-Path $_.FullName 'monitor.pid'
            if (Test-Path $pidFile) {
                try {
                    $procId = [int](Get-Content $pidFile -Raw).Trim()
                    Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
                } catch { }
            }
        }
    }
    Write-Host '  [OK] Daemons stopped.' -ForegroundColor Green

    # 2. Remove Windows logon startup entries
    Write-Host '  [2/5] Removing Windows logon startup entries...' -ForegroundColor Yellow
    $StartupDir = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\Startup'
    if (Test-Path $StartupDir) {
        Get-ChildItem -Path $StartupDir -Filter 'Watchman-*.cmd' | Remove-Item -Force -ErrorAction SilentlyContinue
        Get-ChildItem -Path $StartupDir -Filter 'SentinelFS-*.cmd' | Remove-Item -Force -ErrorAction SilentlyContinue
    }
    Write-Host '  [OK] Startup shortcuts removed.' -ForegroundColor Green

    # 3. Uninstall Python package
    Write-Host '  [3/5] Uninstalling Watchman pip package...' -ForegroundColor Yellow
    $pyCmds = [System.Collections.Generic.List[string]]::new()
    foreach ($c in @('py', 'python3', 'python')) { $pyCmds.Add($c) }
    $userPyDirs = Join-Path $env:LOCALAPPDATA 'Programs\Python'
    if (Test-Path $userPyDirs) {
        Get-ChildItem -Path $userPyDirs -Filter 'python.exe' -Recurse -Depth 2 -ErrorAction SilentlyContinue |
            ForEach-Object { $pyCmds.Add($_.FullName) }
    }

    foreach ($cmd in $pyCmds) {
        try {
            if ($cmd -eq 'py') {
                & py -3 -m pip uninstall -y watchman 2>&1 | Out-Null
            } else {
                & $cmd -m pip uninstall -y watchman 2>&1 | Out-Null
            }
        } catch { }
    }

    # Clean up any lingering watchman.exe from user script folders
    $scriptGlobs = @(
        (Join-Path $env:APPDATA 'Python\Python*\Scripts\watchman*'),
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python*\Scripts\watchman*'),
        (Join-Path $env:LOCALAPPDATA 'Packages\PythonSoftwareFoundation.Python.*\LocalCache\local-packages\Python*\Scripts\watchman*')
    )
    foreach ($g in $scriptGlobs) {
        Get-Item -Path $g -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
    }
    Write-Host '  [OK] Pip package uninstalled.' -ForegroundColor Green

    # 4. Remove stored credentials (keyring)
    Write-Host '  [4/5] Clearing stored credentials...' -ForegroundColor Yellow
    foreach ($cmd in $pyCmds) {
        try {
            $pyScript = "import keyring; [keyring.delete_password('Watchman', s) for s in ['token', 'chat_id'] if True]"
            if ($cmd -eq 'py') { & py -3 -c $pyScript 2>$null } else { & $cmd -c $pyScript 2>$null }
        } catch { }
    }

    # 5. Remove application directories & databases
    Write-Host '  [5/5] Deleting Watchman data and application files...' -ForegroundColor Yellow
    $AppDir = Join-Path $env:LOCALAPPDATA 'Watchman'
    if (Test-Path $AppDir) {
        Remove-Item -Path $AppDir -Recurse -Force -ErrorAction SilentlyContinue
    }
    $OldAppDir = Join-Path $env:LOCALAPPDATA 'SentinelFS'
    if (Test-Path $OldAppDir) {
        Remove-Item -Path $OldAppDir -Recurse -Force -ErrorAction SilentlyContinue
    }
    Write-Host '  [OK] Local application files and logs removed.' -ForegroundColor Green

    Write-Host ''
    Write-Host '  --------------------------------------------------' -ForegroundColor DarkGray
    Write-Host '  [OK] Watchman has been completely removed.' -ForegroundColor Green
    Write-Host '  --------------------------------------------------' -ForegroundColor DarkGray
    Write-Host ''
}
