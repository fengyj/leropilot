#!/usr/bin/env bash
set -euo pipefail

# run-lint.sh — Run lint/static checks for backend and frontend
# - Backend: ruff (check + format check) and mypy (src)
# - Frontend: npm run lint and npm run check:format

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

RUFF_EXEC="${ROOT_DIR}/.venv/bin/ruff"
MYPY_EXEC="${ROOT_DIR}/.venv/bin/mypy"

# Print a concise marker with a fixed label width to keep output aligned.
print_marker() {
  local label="$1"
  local width=20
  printf '======== %-'"${width}"'s ========\n' "${label}"
}

print_marker "ruff: check"
if [ -x "$RUFF_EXEC" ]; then
  "$RUFF_EXEC" check .
elif command -v ruff >/dev/null 2>&1; then
  ruff check .
else
  echo "ruff not found; skipping"
fi
print_marker "ruff: check done"

print_marker "ruff: format"
if [ -x "$RUFF_EXEC" ]; then
  "$RUFF_EXEC" format --check .
elif command -v ruff >/dev/null 2>&1; then
  ruff format --check .
else
  echo "ruff not found; skipping"
fi
print_marker "ruff: format done"

print_marker "mypy"
if [ -x "$MYPY_EXEC" ]; then
  "$MYPY_EXEC" src
elif command -v mypy >/dev/null 2>&1; then
  mypy src
else
  echo "mypy not found; skipping"
fi
print_marker "mypy done"

echo
echo "== Running frontend linters =="
if [ -d "frontend" ]; then
  pushd frontend >/dev/null
  if command -v npm >/dev/null 2>&1; then
    # it's expected you have deps installed; use `npm ci` when needed
    npm run lint
    npm run check:format
  else
    echo "npm not found; skipping frontend lint steps."
  fi
  popd >/dev/null
else
  echo "No frontend directory found; skipping frontend lint."
fi

echo
echo "All requested linters completed (exit code 0 if no errors)."
