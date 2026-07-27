@echo off
REM Azure Cost Data Collection - Quick Run
REM Double-click this file to collect Azure cost data

echo ============================================================
echo Azure Cost Data Collection
echo ============================================================
echo.

cd /d "%~dp0.."
echo Working directory: %CD%
echo.

echo Running data collection...
echo.

python scripts\collect_with_access.py

echo.
echo ============================================================
echo Collection complete!
echo.
echo View dashboard at: http://localhost:3000/d/azure-costs
echo ============================================================
echo.

pause
