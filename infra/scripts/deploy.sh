#!/bin/bash
set -e

PROJECT_DIR="/var/lib/jenkins/workspace/S15P21E206-deploy"

echo "=== Starlight News Deployment Start ==="

cd "$PROJECT_DIR"

docker compose up -d --build --remove-orphans

docker compose ps

echo "=== Starlight News Deployment Complete ==="