import json
from pathlib import Path

from fastapi.testclient import TestClient

import app.articles.service as service
from app.config import settings
from app.database import _driver
from app.main import app

client = TestClient(app)

# AI 실제 모델을 돌려서 만든 응답 예시(ai/test_pipeline에서 복사해옴). starlight_ai 없이 목업으로
# 오케스트레이션 로직(_apply_analysis)을 검증한다 - _call_ai만 이 값을 리턴하게 바꿔치기한다.
MOCK_AI_RESULT_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "starlight_result_server.json"


def _mock_ai_result() -> dict:
    return json.loads(MOCK_AI_RESULT_PATH.read_text(encoding="utf-8"))


# /articles/analyze 엔드포인트 검증. _call_ai만 목업으로 바꾸고, 나머지(Neo4j 반영)는 실제 로컬 Neo4j로 그대로 실행한다.
def test_analyze_article_creates_graph_from_ai_result(monkeypatch):
    monkeypatch.setattr(service, "_call_ai", lambda request: _mock_ai_result())

    test_article_id = 900101
    test_source_id = 900001

    # 이전 실행에서 남은 테스트 기사를 지워서 재실행 가능하게 함
    with _driver.session() as session:
        session.run("MATCH (a:Article {mysqlArticleId: $id}) DETACH DELETE a", id=test_article_id)

    payload = {
        "articleId": test_article_id,
        "title": "서울시, 청년 주거 지원 확대",
        "content": "실제 본문은 _call_ai가 목업으로 대체되어 쓰이지 않는다.",
        "sourceId": test_source_id,
        "sourceName": "테스트뉴스",
        "publishedAt": "2026-09-08T09:00:00+09:00",
    }

    response = client.post(
        "/internal/v1/articles/analyze",
        json=payload,
        headers={"x-internal-api-key": settings.internal_api_key},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["articleId"] == test_article_id
    assert data["status"] == "COMPLETED"
    assert data["primaryTopicCode"] == "ECONOMY"
    assert data["subtopicCode"] == "EMPLOYMENT_STARTUPS"
    article_node_id = data["articleNodeId"]
    assert article_node_id

    # 실제 Neo4j에 노드/엣지가 반영됐는지 직접 확인
    # (목업 기준: Entity 4개, Event 1개, Statement 1개, PUBLISHED_BY 1개, CLASSIFIED_AS 1개)
    with _driver.session() as session:
        record = session.run(
            """
            MATCH (a:Article {nodeId: $articleId})
            OPTIONAL MATCH (a)-[:MENTIONS]->(e:Entity)
            OPTIONAL MATCH (a)-[:COVERS]->(ev:Event)
            OPTIONAL MATCH (a)-[:CONTAINS_STATEMENT]->(s:Statement)
            OPTIONAL MATCH (a)-[:PUBLISHED_BY]->(o:Entity:NewsOrganization)
            OPTIONAL MATCH (a)-[:CLASSIFIED_AS]->(t:Topic)
            RETURN count(DISTINCT e) AS entityCount,
                   count(DISTINCT ev) AS eventCount,
                   count(DISTINCT s) AS statementCount,
                   count(DISTINCT o) AS orgCount,
                   count(DISTINCT t) AS topicCount
            """,
            articleId=article_node_id,
        ).single()

    assert record["entityCount"] == 4
    assert record["eventCount"] == 1
    assert record["statementCount"] == 1
    assert record["orgCount"] == 1
    assert record["topicCount"] == 1


# 같은 기사를 다시 분석 요청해도(재시도 등) 노드가 중복 생성되지 않는지 확인 (멱등성)
def test_analyze_article_is_idempotent_on_retry(monkeypatch):
    monkeypatch.setattr(service, "_call_ai", lambda request: _mock_ai_result())

    test_article_id = 900102
    test_source_id = 900001

    with _driver.session() as session:
        session.run("MATCH (a:Article {mysqlArticleId: $id}) DETACH DELETE a", id=test_article_id)

    payload = {
        "articleId": test_article_id,
        "title": "서울시, 청년 주거 지원 확대",
        "content": "실제 본문은 _call_ai가 목업으로 대체되어 쓰이지 않는다.",
        "sourceId": test_source_id,
        "sourceName": "테스트뉴스",
        "publishedAt": "2026-09-08T09:00:00+09:00",
    }
    headers = {"x-internal-api-key": settings.internal_api_key}

    first = client.post("/internal/v1/articles/analyze", json=payload, headers=headers)
    second = client.post("/internal/v1/articles/analyze", json=payload, headers=headers)

    assert first.status_code == 200
    assert second.status_code == 200
    # 같은 mysqlArticleId로 MERGE되므로 두 번 호출해도 같은 Article nodeId를 돌려줘야 함
    assert first.json()["data"]["articleNodeId"] == second.json()["data"]["articleNodeId"]

    article_node_id = first.json()["data"]["articleNodeId"]
    with _driver.session() as session:
        statement_count = session.run(
            "MATCH (:Article {nodeId: $articleId})-[:CONTAINS_STATEMENT]->(:Statement) RETURN count(*) AS c",
            articleId=article_node_id,
        ).single()["c"]

    # Statement는 CREATE가 아니라 MERGE라, 두 번 분석해도 중복 생성되면 안 됨
    assert statement_count == 1
