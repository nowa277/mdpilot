#!/usr/bin/env bash
# Build and ship mdpilot-frontend image to lab03.
# Usage: scripts/deploy-lab03.sh [tag]
# Requires: docker, ssh access to lab03 with docker installed.
set -euo pipefail

TAG="${1:-latest}"
IMAGE="mdpilot-frontend:${TAG}"
LAB03_HOST="${LAB03_HOST:-lab03}"
LAB03_USER="${LAB03_USER:-mdpilot}"

echo "==> building ${IMAGE}"
docker build -t "${IMAGE}" .

echo "==> exporting and shipping image"
docker save "${IMAGE}" | ssh "${LAB03_USER}@${LAB03_HOST}" 'docker load'

echo "==> restarting frontend container on lab03"
ssh "${LAB03_USER}@${LAB03_HOST}" \
  "docker rm -f mdpilot-frontend >/dev/null 2>&1 || true; \
   docker run -d --name mdpilot-frontend \
     --network mdpilot-net \
     -p 3000:80 \
     --restart unless-stopped \
     ${IMAGE}"

echo "==> done. Frontend reachable at http://${LAB03_HOST}:3000"
