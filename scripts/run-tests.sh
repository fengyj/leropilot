#!/usr/bin/env bash
set -euo pipefail

# run-tests.sh — Run unit tests for backend and frontend
# - Backend: pytest (via uv if available)
# - Frontend: vitest via npm

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

EXIT_CODE=0

echo "== Running backend unit tests =="
if command -v uv >/dev/null 2>&1; then
  uv run python -m pytest --tb=short --strict-markers
else
  if command -v pytest >/dev/null 2>&1; then
    pytest --tb=short --strict-markers
  else
    echo "pytest (or uv) not found — cannot run backend tests"
    EXIT_CODE=2
  fi
fi

if [ $EXIT_CODE -ne 0 ]; then
  echo "Backend tests could not be run. Exiting with code $EXIT_CODE"
  exit $EXIT_CODE
fi

echo
echo "== Running frontend unit tests =="
if [ -d "frontend" ]; then
  pushd frontend >/dev/null
  if command -v npm >/dev/null 2>&1; then
    # ensure dependencies installed for a reliable test run
    npm ci
    npm run test -- --run
  else
    echo "npm not found; skipping frontend tests."
    EXIT_CODE=3
  fi
  popd >/dev/null
else
  echo "No frontend directory found; skipping frontend tests."
fi

exit $EXIT_CODE
