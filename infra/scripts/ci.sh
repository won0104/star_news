#!/bin/bash
set -Eeuo pipefail

PROJECT_DIR="/var/lib/jenkins/workspace/S15P21E206-ci"
# FastAPI Settings 필수값. 서버에만 두고 git에는 올리지 않는다.
ENV_CI_FILE="/home/ubuntu/S15P21E206/.env.ci"

echo "=== Starlight News CI Start ==="

cd "$PROJECT_DIR"

run_in_container() {
    local image="$1"
    local source_dir="$2"
    local inner_script="$3"

    docker run --rm \
        -v "${source_dir}:/src:ro" \
        "$image" \
        sh -c "$inner_script"
}

echo "--- Frontend CI (node:22-alpine) ---"
run_in_container "node:22-alpine" "${PROJECT_DIR}/frontend" '
    set -Eeuo pipefail
    mkdir -p /tmp/app
    cp -a /src/. /tmp/app/
    cd /tmp/app
    npm ci
    npm run lint
    npm run build
'

echo "--- Spring Boot CI (eclipse-temurin:21-jdk) ---"
run_in_container "eclipse-temurin:21-jdk" "${PROJECT_DIR}/backend/spring" '
    set -Eeuo pipefail
    mkdir -p /tmp/app
    cp -a /src/. /tmp/app/
    cd /tmp/app
    chmod +x gradlew
    ./gradlew clean test build --no-daemon
'

echo "--- FastAPI CI (python:3.11-slim) ---"
if [ ! -f "$ENV_CI_FILE" ]; then
    echo "Missing CI env file: $ENV_CI_FILE" >&2
    exit 1
fi

docker run --rm \
    --env-file "$ENV_CI_FILE" \
    -v "${PROJECT_DIR}/backend/fastapi:/src:ro" \
    python:3.11-slim \
    sh -c '
        set -Eeuo pipefail
        mkdir -p /tmp/app
        cp -a /src/. /tmp/app/
        cd /tmp/app
        pip install --no-cache-dir -r requirements.txt

        if python -c "import importlib.util; raise SystemExit(0 if importlib.util.find_spec(\"pytest\") else 1)" 2>/dev/null \
            && find . \( -name "test_*.py" -o -name "*_test.py" \) -print -quit | grep -q .; then
            python -m pytest
        else
            python -m compileall app
        fi
    '

echo "=== Starlight News CI Complete ==="
