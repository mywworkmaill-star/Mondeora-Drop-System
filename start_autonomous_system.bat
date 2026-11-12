@echo off
REM AUTONOMOUS SYSTEM STARTER
REM Starts the self-improving system in background

echo ========================================
echo STARTING AUTONOMOUS SYSTEM
echo ========================================
echo.

cd /d "C:\Users\Administrator\Desktop\Mondeora-Drop-System"

echo Installing required packages...
"C:\Program Files\Python311\python.exe" -m pip install schedule --quiet

echo.
echo Starting autonomous scheduler...
echo System will run in background...
echo.
echo Close this window to stop (or press Ctrl+C)
echo.

"C:\Program Files\Python311\python.exe" autonomous_scheduler.py

pause
