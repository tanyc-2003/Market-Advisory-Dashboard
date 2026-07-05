@echo off
setlocal EnableExtensions
REM ===========================================================================
REM  Market Advisory Dashboard - launcher
REM ---------------------------------------------------------------------------
REM  Double-click this file (or run it from a terminal) to start the dashboard.
REM  By default it launches the CURRENT UI: the FastAPI backend (port 8000) and
REM  the React/Vite frontend (port 5173), each in its own window, and the dev
REM  server opens your browser automatically.
REM
REM  =========================  OPTIONS YOU CAN EDIT  =========================
REM  Change the SET "..." lines in the CONFIG block just below.
REM
REM    UI_MODE            react      -> React web app (current, default)
REM                       streamlit  -> legacy Streamlit UI on port 8501
REM
REM    APP_MODE           v7_lite           -> free data sources (default)
REM                       v7_institutional  -> full layer set; needs Polygon +
REM                                            Sharadar keys in .env (otherwise
REM                                            runs in synthetic "Developer Mode")
REM
REM    LLM_ENABLED        false  -> Query (LLM) page hidden (default)
REM                       true   -> enable it (needs a local Ollama running)
REM
REM    API_PORT           Backend port (default 8000). NOTE: if you change this,
REM                       also update the proxy target in frontend/vite.config.ts
REM                       (or set VITE_API_BASE), or the UI cannot reach the API.
REM
REM    FRONTEND_PORT      Vite dev-server port (default 5173).
REM
REM    RUN_DATA_PIPELINE  no   -> just launch (default)
REM                       yes  -> first ingest real data + train the HMM so the
REM                               market-state / watchlist / sizing panels are
REM                               LIVE instead of representative. Needs internet;
REM                               runs scripts\ingest_real_data.py then
REM                               scripts\train_hmm.py --mode %APP_MODE%.
REM
REM  Once it's running, the watchlist is user-editable: type a ticker in the
REM  Overview and click Add -- it's ingested on the fly (no restart needed).
REM  See docs\10_web_stack.md for the live-vs-representative wiring + the dynamic
REM  watchlist (#dynamic-watchlist), docs\05_running.md for the run recipes, and
REM  README.md for the full configuration reference (.env knobs, paid data, etc).
REM  First-time setup, if the venv is missing:
REM      py -3 -m venv .venv
REM      .venv\Scripts\python -m pip install -e ".[dev,api]"
REM ===========================================================================

REM --------------------------- CONFIG (edit these) ---------------------------
set "UI_MODE=react"
set "APP_MODE=v7_lite"
set "LLM_ENABLED=false"
set "API_PORT=8000"
set "FRONTEND_PORT=5173"
set "RUN_DATA_PIPELINE=no"
REM ---------------------------------------------------------------------------

REM Repo root = the folder this script lives in (strip the trailing backslash).
set "REPO=%~dp0"
if "%REPO:~-1%"=="\" set "REPO=%REPO:~0,-1%"
cd /d "%REPO%"

REM Locate the virtual-env Python.
set "VENV_PY=%REPO%\.venv\Scripts\python.exe"
if not exist "%VENV_PY%" (
  echo [ERROR] Virtual environment not found at:
  echo         %VENV_PY%
  echo.
  echo   Create it first:
  echo       py -3 -m venv .venv
  echo       .venv\Scripts\python -m pip install -e ".[dev,api]"
  echo.
  pause
  exit /b 1
)

REM Make Node / npm visible (typical installer location); harmless if already on PATH.
set "PATH=%ProgramFiles%\nodejs;%PATH%"

REM Export the settings the backend reads via pydantic-settings (config\settings.py).
set "APP_MODE=%APP_MODE%"
set "LLM_ENABLED=%LLM_ENABLED%"

REM Optional one-time data pipeline so the live panels show real data.
if /I "%RUN_DATA_PIPELINE%"=="yes" (
  echo.
  echo === Ingesting real data [yfinance + FRED] and training the HMM ===
  "%VENV_PY%" scripts\ingest_real_data.py
  "%VENV_PY%" scripts\train_hmm.py --mode %APP_MODE%
  echo === Data pipeline done ===
  echo.
)

if /I "%UI_MODE%"=="streamlit" goto :streamlit

REM ============================ React UI (current) ===========================
REM Ensure the backend deps (FastAPI + uvicorn) are installed.
"%VENV_PY%" -c "import fastapi, uvicorn" 2>nul
if errorlevel 1 (
  echo Installing API dependencies [fastapi + uvicorn] ...
  "%VENV_PY%" -m pip install -e ".[api]"
)

REM Ensure the frontend deps are installed (first run only).
if not exist "%REPO%\frontend\node_modules" (
  echo First run: installing frontend dependencies via npm install ...
  pushd "%REPO%\frontend"
  call npm install
  popd
)

echo.
echo Starting API       -^> http://localhost:%API_PORT%
echo Starting frontend  -^> http://localhost:%FRONTEND_PORT%   [opens in your browser]
echo Close the two spawned windows to stop the dashboard.
echo.

REM Each server runs in its own window (cmd /k keeps it open so you can read logs).
start "Market Advisory API" /d "%REPO%" cmd /k .venv\Scripts\python.exe scripts\run_api.py --port %API_PORT%
start "Market Advisory Frontend" /d "%REPO%\frontend" cmd /k npm run dev -- --port %FRONTEND_PORT%
goto :eof

REM ============================ Streamlit UI (legacy) ========================
:streamlit
echo.
echo Starting Streamlit -^> http://localhost:8501   [opens in your browser]
echo Close the spawned window to stop it.
echo.
start "Market Advisory Streamlit" /d "%REPO%" cmd /k .venv\Scripts\python.exe -m streamlit run src\advisory\dashboard\app.py
goto :eof
