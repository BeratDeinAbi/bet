@echo off
echo Starte Sports Prediction Dashboard...

start "Backend" cmd /k "cd /d "%~dp0backend" && "%~dp0.venv\Scripts\uvicorn.exe" main:app --reload --port 8000"

timeout /t 3 /nobreak >nul

start "Frontend" cmd /k "cd /d "%~dp0frontend" && npm run dev"

echo.
echo Backend:  http://localhost:8000
echo Frontend: http://localhost:5173
echo.
echo Beide Fenster schliessen um die Server zu stoppen.
