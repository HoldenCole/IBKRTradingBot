<#
End-of-day push: copy today's logs + state into reports\YYYY-MM-DD\,
commit, push to the current branch on origin. Idempotent (safe to run
twice). Designed to be invoked by Task Scheduler around 17:00 local time.

Requires:
  - Git for Windows with cached credentials (run `git push` once
    interactively first so the credential helper has them).
  - Working tree on the trading branch (not main; we don't want EOD
    snapshots polluting main).

Logs its own activity to logs\eod_push.log.
#>

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
Set-Location $RepoRoot

$LogFile = Join-Path $RepoRoot "logs\eod_push.log"
function Log([string]$msg) {
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $msg"
    Write-Host $line
    Add-Content -Path $LogFile -Value $line
}

try {
    Log "=== EOD push starting ==="
    $today = Get-Date -Format "yyyy-MM-dd"
    $reportDir = Join-Path $RepoRoot "reports\$today"
    New-Item -ItemType Directory -Force -Path $reportDir | Out-Null

    # Copy today's bot log + orders log + state snapshot
    $logsDir = Join-Path $RepoRoot "logs"
    Get-ChildItem -Path $logsDir -Filter "bot_$today.log" -ErrorAction SilentlyContinue |
        Copy-Item -Destination $reportDir -Force
    Get-ChildItem -Path $logsDir -Filter "orders_$today.log" -ErrorAction SilentlyContinue |
        Copy-Item -Destination $reportDir -Force

    $statePath = Join-Path $RepoRoot "state\positions.json"
    if (Test-Path $statePath) {
        Copy-Item $statePath -Destination (Join-Path $reportDir "positions.json") -Force
    }

    # If nothing was copied, still leave a marker so we know the task ran
    $copied = Get-ChildItem -Path $reportDir
    if ($copied.Count -eq 0) {
        Set-Content -Path (Join-Path $reportDir "EMPTY") -Value "no logs or state for $today"
    }

    # Determine current branch
    $branch = (git rev-parse --abbrev-ref HEAD).Trim()
    if ($branch -eq "main") {
        Log "WARN: on main branch; refusing to commit EOD reports to main"
        return
    }
    Log "branch: $branch"

    git add "reports/$today" 2>&1 | Out-Null
    $stagedCount = (git diff --cached --numstat | Measure-Object -Line).Lines
    if ($stagedCount -eq 0) {
        Log "no changes to commit"
    } else {
        git -c user.name="ibkr-bot" -c user.email="bot@local" commit -m "eod report $today" 2>&1 | Out-String | Tee-Object -FilePath $LogFile -Append | Out-Null
        Log "committed"
    }

    Log "pushing to origin/$branch"
    $pushOut = git push origin $branch 2>&1 | Out-String
    Add-Content -Path $LogFile -Value $pushOut
    if ($LASTEXITCODE -ne 0) {
        Log "ERROR: git push failed with exit $LASTEXITCODE"
        exit 1
    }
    Log "=== EOD push done ==="
} catch {
    Log "EXCEPTION: $_"
    exit 1
}
