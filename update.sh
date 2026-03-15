#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

echo ">>> Pulling latest code"
git pull --rebase

echo ">>> Rebuilding and restarting OOT"
docker compose up -d --build

echo ">>> Done"
docker compose ps
