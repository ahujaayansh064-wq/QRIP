@echo off
REM Start QRIP on http://127.0.0.1:8000
python "%~dp0backend\server.py" --demo %*
pause
