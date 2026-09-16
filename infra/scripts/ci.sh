#!/bin/bash
set -Eeuo pipefail

# CI 흐름 (dev 의 MySQL 테스트 전제와 맞춤):
#   FE → FastAPI compileall
#   → CI DB up → Flyway / Neo4j schema
#   → Spring test (compose MySQL, Testcontainers 아님)
#   → FastAPI pytest → cleanup (trap)
#
# Jenkins workspace by default; local smoke: CI_PROJECT_DIR=/path/to/repo
PROJECT_DIR="${CI_PROJECT_DIR:-/var/lib/jenkins/workspace/S15P21E206-ci}"
COMPOSE_FILE="${PROJECT_DIR}/docker-compose.ci.yml"
COMPOSE_PROJECT="s15p21e206-ci"

# CI compose credentials (must match docker-compose.ci.yml)
CI_MYSQL_DB="ci_mysqldb"
CI_MYSQL_USER="ci"
CI_MYSQL_PASSWORD="ci-secret"
CI_MYSQL_ROOT_PASSWORD="ci-root-secret"
CI_NEO4J_USER="neo4j"
CI_NEO4J_PASSWORD="ci-neo4j-secret"
CI_INTERNAL_API_KEY="ci-internal-api-key"
CI_DB_URL="jdbc:mysql://mysql:3306/${CI_MYSQL_DB}?allowPublicKeyRetrieval=true&useSSL=false&serverTimezone=Asia/Seoul&characterEncoding=UTF-8"
CI_DB_DRIVER="com.mysql.cj.jdbc.Driver"

echo "=== Starlight News CI Start ==="
echo "PROJECT_DIR=${PROJECT_DIR}"

cd "$PROJECT_DIR"

run_in_container() {
    local image="$1"
    local source_dir="$2"
    local inner_script="$3"
    shift 3 || true
    # remaining args: extra docker run flags (e.g. --network, -e)
    docker run --rm "$@" \
        -v "${source_dir}:/src:ro" \
        "$image" \
        sh -c "$inner_script"
}

compose_ci() {
    docker compose -p "$COMPOSE_PROJECT" -f "$COMPOSE_FILE" "$@"
}

cleanup_ci_db() {
    echo "--- CI DB cleanup ---"
    if [[ -f "$COMPOSE_FILE" ]]; then
        compose_ci down -v --remove-orphans || true
    fi
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

echo "--- FastAPI CI / Unit (python:3.11-slim, compileall) ---"
run_in_container "python:3.11-slim" "${PROJECT_DIR}/backend/fastapi" '
    set -Eeuo pipefail
    mkdir -p /tmp/app
    cp -a /src/. /tmp/app/
    cd /tmp/app
    pip install --no-cache-dir -r requirements.txt
    python -m compileall app
'

# ----- MySQL + Neo4j (Spring / FastAPI 공통) -----
if [[ ! -f "$COMPOSE_FILE" ]]; then
    echo "ERROR: missing ${COMPOSE_FILE}"
    exit 1
fi

trap cleanup_ci_db EXIT

echo "--- CI DB up (docker-compose.ci.yml) ---"
compose_ci up -d --wait

echo "--- MySQL schema (Flyway migrate) ---"
docker run --rm \
    --network "${COMPOSE_PROJECT}_default" \
    -v "${PROJECT_DIR}/backend/spring/src/main/resources/db/migration:/flyway/sql:ro" \
    flyway/flyway:10.22.0 \
    -url="jdbc:mysql://mysql:3306/${CI_MYSQL_DB}?allowPublicKeyRetrieval=true&useSSL=false" \
    -user="${CI_MYSQL_USER}" \
    -password="${CI_MYSQL_PASSWORD}" \
    -connectRetries=20 \
    migrate

echo "--- Neo4j schema (V1 + V2 + V3) ---"
compose_ci exec -T neo4j \
    cypher-shell -u "$CI_NEO4J_USER" -p "$CI_NEO4J_PASSWORD" \
    < "${PROJECT_DIR}/backend/fastapi/migrations/neo4j/V1__initial_graph_schema.cypher"

compose_ci exec -T neo4j \
    cypher-shell -u "$CI_NEO4J_USER" -p "$CI_NEO4J_PASSWORD" \
    < "${PROJECT_DIR}/backend/fastapi/migrations/neo4j/V2__event_vector_index.cypher"

compose_ci exec -T neo4j \
    cypher-shell -u "$CI_NEO4J_USER" -p "$CI_NEO4J_PASSWORD" \
    < "${PROJECT_DIR}/backend/fastapi/migrations/neo4j/V3__story_vector_index.cypher"

echo "--- Spring Boot CI (compose MySQL + Neo4j, no Testcontainers) ---"
run_in_container "eclipse-temurin:21-jdk" "${PROJECT_DIR}/backend/spring" '
    set -Eeuo pipefail
    mkdir -p /tmp/app
    cp -a /src/. /tmp/app/
    cd /tmp/app
    chmod +x gradlew
    ./gradlew clean test assemble --no-daemon
' \
    --network "${COMPOSE_PROJECT}_default" \
    -e "DB_URL=${CI_DB_URL}" \
    -e "DB_DRIVER=${CI_DB_DRIVER}" \
    -e "DB_USERNAME=${CI_MYSQL_USER}" \
    -e "DB_PASSWORD=${CI_MYSQL_PASSWORD}" \
    -e "JPA_DDL_AUTO=validate" \
    -e "FLYWAY_ENABLED=true" \
    -e "NEO4J_URI=bolt://neo4j:7687" \
    -e "NEO4J_USERNAME=${CI_NEO4J_USER}" \
    -e "NEO4J_PASSWORD=${CI_NEO4J_PASSWORD}"

echo "--- FastAPI CI / Integration (pytest + Neo4j) ---"
run_in_container "python:3.11-slim" "${PROJECT_DIR}/backend/fastapi" '
    set -Eeuo pipefail
    mkdir -p /tmp/app
    cp -a /src/. /tmp/app/
    cd /tmp/app
    pip install --no-cache-dir -r requirements.txt
    python -m pytest -q
' \
    --network "${COMPOSE_PROJECT}_default" \
    -e "INTERNAL_API_KEY=${CI_INTERNAL_API_KEY}" \
    -e "NEO4J_URI=bolt://neo4j:7687" \
    -e "NEO4J_USERNAME=${CI_NEO4J_USER}" \
    -e "NEO4J_PASSWORD=${CI_NEO4J_PASSWORD}"

echo "=== Starlight News CI Complete ==="
