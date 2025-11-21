#!/bin/bash
# Development startup script for LeRoPilot Electron app

echo "Starting LeRoPilot Development Environment..."

# Start frontend dev server in background
echo "[1/2] Starting Vite dev server..."
cd frontend
npm run dev &
VITE_PID=$!
cd ..

# Wait for Vite to start
echo "Waiting for Vite to start..."
sleep 3

# Start Python backend
echo "[2/2] Starting Python backend..."
python -m leropilot.main --port 8000 --no-browser &
PYTHON_PID=$!

echo ""
echo "✓ Development servers started!"
echo "  - Frontend: http://localhost:5173"
echo "  - Backend:  http://localhost:8000"
echo ""
echo "Now you can:"
echo "  1. Press F5 in VS Code to start Electron debugger"
echo "  2. Or run: cd electron && npm start"
echo ""
echo "Press Ctrl+C to stop all servers"

# Wait for Ctrl+C
trap "kill $VITE_PID $PYTHON_PID 2>/dev/null; exit" INT
wait
