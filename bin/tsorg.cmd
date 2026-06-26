@echo off
setlocal enabledelayedexpansion
rem tsorg - organize wrapper for Windows. Keep this file ASCII-only: cmd.exe
rem mis-tokenizes non-ASCII bytes under chcp 65001 and breaks parsing.
rem Adaptive: when config.wsl.json exists, run the tool inside WSL so it can
rem reach a local ollama over native localhost. Windows-to-WSL HTTP POST is
rem unreliable for sustained calls, so the tool itself runs inside WSL.
rem Otherwise run native Windows python.
for /f "tokens=2 delims=:" %%a in ('chcp') do set "_cp=%%a"
chcp 65001 >nul
if exist "%~dp0..\config.wsl.json" (
    for /f "delims=" %%p in ('wsl wslpath -a "%~dp0.."') do set "REPO=%%p"
    wsl -e bash -lc "cd '!REPO!' && python3 cli.py organize --config config.wsl.json --verbose %*"
) else (
    set "PYTHONUTF8=1"
    python "%~dp0..\cli.py" organize --config "%~dp0..\config.local.json" --verbose %*
)
set "_rc=!errorlevel!"
chcp %_cp% >nul
exit /b %_rc%
