<#
One-shot Windows installer for the IBKR trading bot.

What it does:
  1. Verifies Python 3.11+ is available
  2. Creates a virtualenv at .venv\
  3. Installs the bot (pip install -e .)
  4. Generates a .env file from .env.example if one doesn't exist
  5. Registers a "logon" scheduled task that runs the bot, auto-restarts on crash
  6. Registers a daily scheduled task at -EodLocalTime that pushes the
     day's logs + state to GitHub under reports\YYYY-MM-DD\

Usage (from PowerShell as your user, NOT admin):
  .\scripts\install.ps1                   # default EOD time 17:00 local
  .\scripts\install.ps1 -EodLocalTime "16:45"

Prereqs:
  - IB Gateway installed and configured (port 4002, Read-Only API off)
  - Python 3.11 or newer (https://www.python.org/downloads/)
  - Git for Windows with credential helper enabled (default install is fine)
  - You have run `git push` interactively at least once on this repo so
    your GitHub credentials are cached
  - You have created your .env (the script will template one if missing)

After install:
  - Bot starts automatically at next logon, or run manually:
      Start-ScheduledTask -TaskName "IBKRBot"
  - View bot status:
      Get-ScheduledTaskInfo -TaskName "IBKRBot"
  - View logs:
      Get-Content logs\bot_*.log -Tail 50 -Wait
  - Pull updates:
      .\scripts\update_bot.cmd
  - Uninstall:
      .\scripts\uninstall.ps1
#>

[CmdletBinding()]
param(
    [string]$EodLocalTime = "17:00",
    [string]$BotTaskName = "IBKRBot",
    [string]$EodTaskName = "IBKRBot-EodPush"
)

$ErrorActionPreference = "Stop"

# Resolve repo root (assumes this script lives in <repo>\scripts\)
$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
Set-Location $RepoRoot
Write-Host "[install] Repo root: $RepoRoot" -ForegroundColor Cyan

# 1. Locate Python 3.11+
function Get-PythonExe {
    foreach ($cmd in @("python", "py -3.11", "py -3.12", "py -3.13")) {
        try {
            $parts = $cmd -split " "
            $exe = $parts[0]
            $args = $parts[1..($parts.Count - 1)]
            $version = & $exe @args -c "import sys; print(f'{sys.version_info[0]}.{sys.version_info[1]}')" 2>$null
            if ($LASTEXITCODE -eq 0 -and $version) {
                $major, $minor = $version.Trim().Split(".")
                if ([int]$major -eq 3 -and [int]$minor -ge 11) {
                    return @{ Exe = $exe; Args = $args; Version = $version }
                }
            }
        } catch {}
    }
    return $null
}

$py = Get-PythonExe
if (-not $py) {
    Write-Error "Python 3.11+ not found. Install from https://www.python.org/downloads/"
    exit 1
}
Write-Host "[install] Using Python $($py.Version)" -ForegroundColor Cyan

# 2. Create venv
$VenvPath = Join-Path $RepoRoot ".venv"
if (-not (Test-Path $VenvPath)) {
    Write-Host "[install] Creating virtualenv at $VenvPath" -ForegroundColor Cyan
    & $py.Exe @($py.Args + @("-m", "venv", $VenvPath))
    if ($LASTEXITCODE -ne 0) { throw "venv creation failed" }
} else {
    Write-Host "[install] Using existing virtualenv" -ForegroundColor Yellow
}

$VenvPython = Join-Path $VenvPath "Scripts\python.exe"
$VenvPip = Join-Path $VenvPath "Scripts\pip.exe"

# 3. Install dependencies
Write-Host "[install] Installing dependencies (this takes a minute)..." -ForegroundColor Cyan
& $VenvPython -m pip install --upgrade pip --quiet
if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed" }
& $VenvPip install -e . --quiet
if ($LASTEXITCODE -ne 0) { throw "pip install -e . failed" }

# 4. .env template
$EnvFile = Join-Path $RepoRoot ".env"
if (-not (Test-Path $EnvFile)) {
    Copy-Item (Join-Path $RepoRoot ".env.example") $EnvFile
    Write-Host "[install] Created .env from .env.example. EDIT IT before starting the bot:" -ForegroundColor Yellow
    Write-Host "          $EnvFile" -ForegroundColor Yellow
    Write-Host "          (set FMP_API_KEY, set ECON_CALENDAR_PROVIDER=fmp)" -ForegroundColor Yellow
} else {
    Write-Host "[install] .env exists, leaving alone" -ForegroundColor Yellow
}

# 5. Make sure logs/ and state/ exist
New-Item -ItemType Directory -Force -Path (Join-Path $RepoRoot "logs") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $RepoRoot "state") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $RepoRoot "reports") | Out-Null

# 6. Register the bot scheduled task (run at logon, auto-restart on failure)
$BotCmd = Join-Path $RepoRoot "scripts\run_bot.cmd"

Write-Host "[install] Registering scheduled task '$BotTaskName' (start at logon, auto-restart)" -ForegroundColor Cyan
$action = New-ScheduledTaskAction -Execute $BotCmd -WorkingDirectory $RepoRoot
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -RestartCount 999 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit (New-TimeSpan -Days 0) `
    -MultipleInstances IgnoreNew
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive

if (Get-ScheduledTask -TaskName $BotTaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $BotTaskName -Confirm:$false
}
Register-ScheduledTask -TaskName $BotTaskName -Action $action -Trigger $trigger `
    -Settings $settings -Principal $principal | Out-Null

# 7. Register the EOD push task
$EodScript = Join-Path $RepoRoot "scripts\eod_push.ps1"
$psExe = (Get-Command powershell.exe).Source
$eodArgs = "-NoProfile -ExecutionPolicy Bypass -File `"$EodScript`""

Write-Host "[install] Registering scheduled task '$EodTaskName' (daily at $EodLocalTime local)" -ForegroundColor Cyan
$eodAction = New-ScheduledTaskAction -Execute $psExe -Argument $eodArgs -WorkingDirectory $RepoRoot
$eodTrigger = New-ScheduledTaskTrigger -Daily -At $EodLocalTime
$eodSettings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 10)

if (Get-ScheduledTask -TaskName $EodTaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $EodTaskName -Confirm:$false
}
Register-ScheduledTask -TaskName $EodTaskName -Action $eodAction -Trigger $eodTrigger `
    -Settings $eodSettings -Principal $principal | Out-Null

Write-Host ""
Write-Host "[install] Done." -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Green
Write-Host "  1. Edit .env (set FMP_API_KEY, ECON_CALENDAR_PROVIDER=fmp)"
Write-Host "  2. Confirm IB Gateway is running, logged into PAPER, port 4002"
Write-Host "  3. Smoke test:"
Write-Host "       .\.venv\Scripts\python.exe -m src.main --check-connection"
Write-Host "  4. Start the bot now (otherwise it runs at next logon):"
Write-Host "       Start-ScheduledTask -TaskName '$BotTaskName'"
Write-Host "  5. Tail the log:"
Write-Host "       Get-Content logs\bot_*.log -Tail 50 -Wait"
