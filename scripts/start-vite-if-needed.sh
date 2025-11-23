#!/bin/bash
# Check if Vite is already running, if not, start it

if curl -s http://localhost:5173 > /dev/null 2>&1; then
    echo "✓ Vite is already running on http://localhost:5173"
    exit 0
else
    echo "Starting Vite dev server..."
    cd "$(dirname "$0")/../frontend"
    exec npm run dev
fi
