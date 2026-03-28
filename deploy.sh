#!/usr/bin/env bash
set -euo pipefail

IMAGE="${IMAGE:-ghcr.io/raynertjx/cs4221-chase:latest}"
CONTAINER_NAME="${CONTAINER_NAME:-cs4221-chase}"
HOST_PORT="${PORT:-8080}"
CONTAINER_PORT="${CONTAINER_PORT:-8080}"
GHCR_USERNAME="${GHCR_USERNAME:-}"
GHCR_TOKEN="${GHCR_TOKEN:-}"

if [[ -n "$GHCR_USERNAME" && -n "$GHCR_TOKEN" ]]; then
  echo "$GHCR_TOKEN" | docker login ghcr.io -u "$GHCR_USERNAME" --password-stdin
fi

docker pull "$IMAGE"
docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
docker run -d \
  --name "$CONTAINER_NAME" \
  --restart unless-stopped \
  -p "${HOST_PORT}:${CONTAINER_PORT}" \
  "$IMAGE"
