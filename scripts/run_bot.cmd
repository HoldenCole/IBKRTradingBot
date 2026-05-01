@echo off
REM Bot launcher invoked by Task Scheduler at logon.
REM Sits in a loop: run bot -> on exit, wait 5s, run again.
REM Task Scheduler also has its own restart-on-failure as a safety net.

setlocal
cd /d "%~dp0\.."

set VENV_PY=%CD%\.venv\Scripts\python.exe

if not exist "%VENV_PY%" (
    echo [run_bot] ERROR: %VENV_PY% not found. Run scripts\install.ps1 first. >> logs\launcher.log
    exit /b 1
)

:loop
echo [run_bot] starting bot at %DATE% %TIME% >> logs\launcher.log
"%VENV_PY%" -m src.main --strategy all
echo [run_bot] bot exited with code %ERRORLEVEL% at %DATE% %TIME% >> logs\launcher.log
timeout /t 5 /nobreak > nul
goto loop
