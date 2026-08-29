#!/usr/bin/env bash
set -euo pipefail
./scripts/preflight.sh
docker compose -f deploy/docker-compose.prod.yml up -d --build

