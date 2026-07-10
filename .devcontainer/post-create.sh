#!/usr/bin/env bash
set -euo pipefail

echo "==> Installing runtime dependencies"
pip install --user --no-cache-dir -r requirements.txt

echo "==> Installing package in editable mode"
pip install --user --no-cache-dir -e .

if [ ! -f .env ]; then
  echo "==> Creating .env from .env.example (fill in your secrets!)"
  cp .env.example .env
fi

echo ""
echo "✅ Devcontainer ready."
echo "   Fill in .env, then try:  python -m paperless_finom.cli sync --dry-run --json"
