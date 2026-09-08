#!/bin/bash
set -e

PROJECT_DIR="/var/lib/jenkins/workspace/S15P21E206-deploy"
ENV_FILE="/home/ubuntu/S15P21E206/.env"

echo "=== Starlight News Deployment Start ==="

cd "$PROJECT_DIR"

if [ ! -f "$ENV_FILE" ]; then
    echo "ERROR: deployment env file not found: $ENV_FILE"
    exit 1
fi

docker compose --env-file "$ENV_FILE" config --quiet

docker compose --env-file "$ENV_FILE" up -d --build --remove-orphans

docker compose --env-file "$ENV_FILE" ps

echo "=== Starlight News Deployment Complete ==="
