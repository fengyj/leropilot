@echo off
REM Check if Vite is already running, if not, start it

REM Tolerate stray trailing double-quote argument that VS Code sometimes appends
REM e.g. the debug launcher can produce a final '"' which causes parsing errors
if "%~1"=="" (
    shift
)
if "%~1"=="\"" (
    shift
)

curl -s http://localhost:5173 > nul 2>&1
if %errorlevel% == 0 (
    echo ✓ Vite is already running on http://localhost:5173
    exit /b 0
) else (
    echo Starting Vite dev server...
    cd /d "%~dp0\..\frontend"
    REM If dependencies are missing, do a clean install skipping optional packages which can include incompatible native binaries
    if not exist "node_modules" (
        echo Installing dependencies (skipping optional packages)...
        npm ci --no-optional
    )

    REM Run dev; if it fails due to optional native modules, reinstall without optional deps and retry once
    npm run dev || (
        echo npm run dev failed; reinstalling without optional packages and retrying...
        npm install --no-optional
        npm run dev
    )
)