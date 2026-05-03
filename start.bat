@echo off
echo ============================================
echo  Sports Prediction Dashboard
echo ============================================
echo.

set ROOT=%~dp0

echo [1/3] Python-Pakete pruefen...
"%ROOT%.venv\Scripts\pip.exe" install -r "%ROOT%backend\requirements.txt" -q --disable-pip-version-check
echo       OK

echo [2/3] Node-Pakete pruefen...
cd /d "%ROOT%frontend"
npm install --silent 2>nul
echo       OK

echo [3/3] Server starten...
start "Backend  (http://localhost:8000)" cmd /k "cd /d "%ROOT%backend" && "%ROOT%.venv\Scripts\uvicorn.exe" main:app --reload --port 8000"
timeout /t 2 /nobreak >nul
start "Frontend (http://localhost:5173)" cmd /k "cd /d "%ROOT%frontend" && npm run dev"

echo.
echo  Frontend: http://localhost:5173
echo  Backend:  http://localhost:8000
echo.
echo  Fenster schliessen = Server stoppen.
echo.
pause
