@echo off
setlocal
set "PYTHONUTF8=1"
for /f "tokens=2 delims=:" %%a in ('chcp') do set "_cp=%%a"
chcp 65001 >nul
python "%~dp0..\cli.py" status %*
set "_rc=%errorlevel%"
chcp %_cp% >nul
exit /b %_rc%
