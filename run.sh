#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

echo ">>> Starting OOT with Docker Compose"
docker compose up -d --build

echo ">>> OOT is starting"
echo "Local:   http://localhost:8502"
echo "Network: http://$(hostname -I | awk '{print $1}'):8502"
