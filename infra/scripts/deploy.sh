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

# 데이터 서비스는 재생성하지 않고 기동·health 상태만 보장한다.
docker compose --env-file "$ENV_FILE" up -d --wait mysql neo4j redis

# AI 서비스도 같은 compose 파일에 있지만 일반 앱과 배포 수명 주기는 다르다.
# 여기서는 AI를 만들거나 재기동하지 않고, 이미 떠 있는 워커가 준비됐는지만 확인한다.
# 별도 AI 배포가 누락됐으면 FastAPI를 올리기 전에 실패시켜 반쪽 배포를 방지한다.
if ! docker compose --env-file "$ENV_FILE" exec -T ai-worker \
    python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8100/ready', timeout=3)"; then
    echo "ERROR: AI worker is not ready. Run infra/scripts/deploy-ai.sh first."
    exit 1
fi

# 앱 이미지만 갱신한다. --no-deps는 backend-fastapi의 의존 서비스인 ai-worker를
# Compose가 함께 재생성하지 못하게 막는다. 같은 이유로 --remove-orphans도 사용하지 않는다.
docker compose --env-file "$ENV_FILE" build frontend backend-spring backend-fastapi
docker compose --env-file "$ENV_FILE" up -d --no-deps frontend backend-spring backend-fastapi

docker compose --env-file "$ENV_FILE" ps frontend backend-spring backend-fastapi ai-worker

echo "=== Starlight News Deployment Complete ==="
