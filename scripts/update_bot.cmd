@echo off
REM Pull latest code from current branch and restart the bot.
REM Run this when there are new commits to pick up.

setlocal
cd /d "%~dp0\.."

echo [update] fetching origin
git fetch origin
if errorlevel 1 (
    echo [update] git fetch failed
    exit /b 1
)

for /f "delims=" %%b in ('git rev-parse --abbrev-ref HEAD') do set BRANCH=%%b
echo [update] current branch: %BRANCH%

echo [update] pulling
git pull --ff-only origin %BRANCH%
if errorlevel 1 (
    echo [update] git pull failed; resolve manually
    exit /b 1
)

echo [update] reinstalling dependencies
.venv\Scripts\pip.exe install -e . --quiet
if errorlevel 1 (
    echo [update] pip install failed
    exit /b 1
)

echo [update] restarting bot
schtasks /End /TN "IBKRBot" 2>nul
timeout /t 3 /nobreak > nul
schtasks /Run /TN "IBKRBot"
if errorlevel 1 (
    echo [update] failed to restart task. Start manually with:
    echo          Start-ScheduledTask -TaskName 'IBKRBot'
    exit /b 1
)
echo [update] done
