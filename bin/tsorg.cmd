@echo off
setlocal enabledelayedexpansion
for /f "tokens=2 delims=:" %%a in ('chcp') do set "_cp=%%a"
chcp 65001 >nul
if exist "%~dp0..\config.wsl.json" (
    rem WSL 上のローカル LLM をネイティブ localhost で叩く（Windows<->WSL 境界越しの
    rem POST は連続実行で不安定なため、ツール自体を WSL 内で実行する）
    for /f "delims=" %%p in ('wsl wslpath -a "%~dp0.."') do set "REPO=%%p"
    wsl -e bash -lc "cd '!REPO!' && python3 cli.py organize --config config.wsl.json --verbose %*"
) else (
    set "PYTHONUTF8=1"
    python "%~dp0..\cli.py" organize --config "%~dp0..\config.local.json" --verbose %*
)
set "_rc=!errorlevel!"
chcp %_cp% >nul
exit /b %_rc%
