#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
docker compose -f backend/compose.yaml --profile build-only build
docker compose -f backend/compose.yaml up -d --wait
