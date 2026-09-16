#!/bin/bash
set -e

PROJECT_DIR="/var/lib/jenkins/workspace/S15P21E206-deploy"
ENV_FILE="/home/ubuntu/S15P21E206/.env"

echo "=== Starlight AI Worker Deployment Start ==="

cd "$PROJECT_DIR"

if [ ! -f "$ENV_FILE" ]; then
    echo "ERROR: deployment env file not found: $ENV_FILE"
    exit 1
fi

docker compose --env-file "$ENV_FILE" config --quiet

# 모델 가중치는 빌드 산출물이 아니다. 기존 외부 volume이 없으면 다운로드를
# 암묵적으로 시작하지 않고 운영자가 모델 준비 절차를 먼저 수행하게 한다.
if ! docker volume inspect ai-cpu-models >/dev/null 2>&1; then
    echo "ERROR: model volume not found: ai-cpu-models"
    exit 1
fi

# AI 코드나 의존성이 바뀐 경우에만 이 스크립트를 직접 실행한다.
# 아래 up 명령은 기존 워커를 새 이미지로 교체하므로 모델도 RAM에 다시 로드된다.
# 모델 volume은 컨테이너 밖에 남아 있어 가중치를 다시 다운로드하지 않는다.
docker compose --env-file "$ENV_FILE" build ai-worker
docker compose --env-file "$ENV_FILE" up -d --no-deps --wait ai-worker

docker compose --env-file "$ENV_FILE" ps ai-worker

echo "=== Starlight AI Worker Deployment Complete ==="
