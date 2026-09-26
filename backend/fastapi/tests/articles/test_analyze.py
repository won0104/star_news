import json
import math
from pathlib import Path
from uuid import UUID

import pytest
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


def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _normalize(a: list[float]) -> list[float]:
    norm = math.sqrt(_dot(a, a))
    return [x / norm for x in a]


# base와 정확히 원하는 "Neo4j 벡터 인덱스 score"를 갖는 새 unit vector를 만든다 (numpy 없이 순수 파이썬으로)
# 실측 확인: Neo4j cosine 인덱스의 score는 순수 코사인이 아니라 (1 + 코사인) / 2 로 변환된 값이라,
# 원하는 score를 만들려면 그에 대응하는 raw cosine(=2*score-1)을 먼저 구해서 합성해야 한다.
# base·cos + 직교성분·sin으로 합성하면 base와의 내적(raw cosine)이 정확히 그 값이 됨
def _vector_with_similarity(base: list[float], target_score: float) -> list[float]:
    base = _normalize(base)
    raw = [1.0 if i % 2 == 0 else -1.0 for i in range(len(base))]
    dot = _dot(raw, base)
    orthogonal = _normalize([r - dot * b for r, b in zip(raw, base)])
    target_cosine = 2 * target_score - 1
    other_weight = math.sqrt(max(0.0, 1 - target_cosine**2))
    return [target_cosine * b + other_weight * o for b, o in zip(base, orthogonal)]


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
    assert str(UUID(article_node_id)) == article_node_id

    # 실제 Neo4j에 노드/엣지가 반영됐는지 직접 확인
    # (목업 기준: Entity 4개, Event 1개, Statement 1개, PUBLISHED_BY 1개, CLASSIFIED_AS 1개)
    with _driver.session() as session:
        record = session.run(
            """
            MATCH (a:Article {nodeId: $articleId})
            OPTIONAL MATCH (a)-[:MENTIONS]->(e:Entity)
            OPTIONAL MATCH (a)-[covers:COVERS]->(ev:Event)
            OPTIONAL MATCH (a)-[:CONTAINS_STATEMENT]->(s:Statement)
            OPTIONAL MATCH (a)-[:PUBLISHED_BY]->(o:Entity:NewsOrganization)
            OPTIONAL MATCH (a)-[:CLASSIFIED_AS]->(t:Topic)
            RETURN count(DISTINCT e) AS entityCount,
                   count(DISTINCT ev) AS eventCount,
                   count(DISTINCT CASE WHEN covers.isPrimary = true THEN ev END) AS primaryEventCount,
                   count(DISTINCT s) AS statementCount,
                   count(DISTINCT o) AS orgCount,
                   count(DISTINCT t) AS topicCount
            """,
            articleId=article_node_id,
        ).single()

    assert record["entityCount"] == 4
    assert record["eventCount"] == 1
    assert record["primaryEventCount"] == 1
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
        counts = session.run(
            """
            MATCH (a:Article {nodeId: $articleId})
            OPTIONAL MATCH (a)-[:CONTAINS_STATEMENT]->(s:Statement)
            OPTIONAL MATCH (a)-[c:COVERS]->(:Event)
            RETURN count(DISTINCT s) AS statements,
                   count(DISTINCT CASE WHEN c.isPrimary = true THEN c END) AS primaryCovers
            """,
            articleId=article_node_id,
        ).single()

    # 재분석해도 Statement나 primary COVERS가 중복 생성되면 안 됨
    assert counts["statements"] == 1
    assert counts["primaryCovers"] == 1


def test_analyze_article_rejects_legacy_non_uuid_collision(monkeypatch):
    monkeypatch.setattr(service, "_call_ai", lambda request: _mock_ai_result())

    test_article_id = 900103
    legacy_node_id = "ART-legacy-collision-test"
    original_title = "2024 레거시 기사"
    payload = {
        "articleId": test_article_id,
        "title": "2026 운영 기사",
        "content": "실제 본문은 _call_ai가 목업으로 대체되어 쓰이지 않는다.",
        "sourceId": 900001,
        "sourceName": "테스트뉴스",
        "publishedAt": "2026-09-08T09:00:00+09:00",
    }

    with _driver.session() as session:
        session.run("MATCH (a:Article {mysqlArticleId: $id}) DETACH DELETE a", id=test_article_id)
        session.run(
            """
            CREATE (:Article {
                nodeId: $nodeId,
                mysqlArticleId: $mysqlArticleId,
                title: $title,
                publishedAt: datetime('2024-01-01T09:00:00+09:00')
            })
            """,
            nodeId=legacy_node_id,
            mysqlArticleId=test_article_id,
            title=original_title,
        )

    try:
        response = client.post(
            "/internal/v1/articles/analyze",
            json=payload,
            headers={"x-internal-api-key": settings.internal_api_key},
        )

        assert response.status_code == 409
        assert response.json()["code"] == "ARTICLE_IDENTITY_CONFLICT"

        # 충돌 감지 전에 실행된 Article SET도 트랜잭션과 함께 롤백되어야 한다.
        with _driver.session() as session:
            record = session.run(
                """
                MATCH (a:Article {mysqlArticleId: $id})
                RETURN a.nodeId AS nodeId, a.title AS title, a.analyzedAt AS analyzedAt
                """,
                id=test_article_id,
            ).single()
        assert record["nodeId"] == legacy_node_id
        assert record["title"] == original_title
        assert record["analyzedAt"] is None
    finally:
        with _driver.session() as session:
            session.run("MATCH (a:Article {mysqlArticleId: $id}) DETACH DELETE a", id=test_article_id)


# Event.title/embedding만 바꾼 목업을 만든다 (같은 Topic/Entity 등은 그대로 재사용)
def _mock_ai_result_with_event(title: str, embedding: list[float]) -> dict:
    result = _mock_ai_result()
    for node in result["nodes"]:
        if "Event" in node["labels"]:
            node["properties"]["title"] = title
            node["properties"]["embedding"] = embedding
    return result


# 서로 다른 기사의 Event 둘이 "같은 사건(Event dedup)"은 아니지만 "같은 흐름"일 만큼 유사하면,
# 둘 다 외톨이 상태에서 만나 하나의 Story로 승격되는지 확인 (B안 핵심 시나리오)
def test_two_related_events_get_promoted_into_shared_story(monkeypatch):
    test_article_id_1 = 900301
    test_article_id_2 = 900302
    test_source_id = 900001

    with _driver.session() as session:
        session.run(
            "MATCH (a:Article) WHERE a.mysqlArticleId IN [$id1, $id2] DETACH DELETE a",
            id1=test_article_id_1,
            id2=test_article_id_2,
        )

    base_mock = _mock_ai_result()
    base_event_node = next(n for n in base_mock["nodes"] if "Event" in n["labels"])
    base_embedding = base_event_node["properties"]["embedding"]
    # Event dedup 임계값(0.92)보다 낮고 Story 임계값(0.80)보다는 높은 유사도 - "다른 사건, 같은 흐름"
    related_embedding = _vector_with_similarity(base_embedding, 0.85)

    headers = {"x-internal-api-key": settings.internal_api_key}

    monkeypatch.setattr(
        service, "_call_ai", lambda request: _mock_ai_result_with_event("1차 발표", base_embedding)
    )
    first = client.post(
        "/internal/v1/articles/analyze",
        json={
            "articleId": test_article_id_1,
            "title": "청년 주거 지원 1차 발표",
            "content": "목업 대체",
            "sourceId": test_source_id,
            "sourceName": "테스트뉴스",
            "publishedAt": "2026-09-08T09:00:00+09:00",
        },
        headers=headers,
    )
    assert first.status_code == 200

    monkeypatch.setattr(
        service, "_call_ai", lambda request: _mock_ai_result_with_event("후속 조치 발표", related_embedding)
    )
    second = client.post(
        "/internal/v1/articles/analyze",
        json={
            "articleId": test_article_id_2,
            "title": "청년 주거 지원 후속 조치",
            "content": "목업 대체",
            "sourceId": test_source_id,
            "sourceName": "테스트뉴스",
            "publishedAt": "2026-09-15T09:00:00+09:00",
        },
        headers=headers,
    )
    assert second.status_code == 200

    with _driver.session() as session:
        story_ids = session.run(
            """
            MATCH (a:Article)-[:COVERS]->(:Event)-[:PART_OF]->(s:Story)
            WHERE a.mysqlArticleId IN [$id1, $id2]
            RETURN DISTINCT s.nodeId AS storyId
            """,
            id1=test_article_id_1,
            id2=test_article_id_2,
        ).value()

    # 둘 다 정확히 같은 Story 하나로 묶여야 함 (승격 시나리오)
    assert len(story_ids) == 1


# v3 모델이 COVERS에 isPrimary를 주면 UUID 순서 대신 그 Event를 primary로 저장하는지 확인.
# 어느 쪽을 골라도 맞아야 하므로 두 경우를 모두 돌린다 (UUID 순서 규칙이면 한쪽은 실패한다).
@pytest.mark.parametrize("primary_index", [0, 1])
def test_analyze_article_uses_model_covers_primary(monkeypatch, primary_index):
    test_article_id = 900401 + primary_index
    test_source_id = 900001

    with _driver.session() as session:
        session.run("MATCH (a:Article {mysqlArticleId: $id}) DETACH DELETE a", id=test_article_id)

    result = _mock_ai_result()
    article_ai_id = next(n for n in result["nodes"] if "Article" in n["labels"])["properties"]["nodeId"]
    base_event = next(n for n in result["nodes"] if "Event" in n["labels"])
    base_embedding = base_event["properties"]["embedding"]
    # 두 Event가 dedup(0.92)되거나 같은 Story로 묶이지 않을 만큼 다른 벡터
    second_event = json.loads(json.dumps(base_event))
    second_event["properties"]["nodeId"] = "EFR-v3-second"
    second_event["properties"]["title"] = "김민수 주거정책과장은 다음 달부터 신청을 받는다"
    second_event["properties"]["embedding"] = _vector_with_similarity(base_embedding, 0.3)
    result["nodes"].append(second_event)

    event_ids = [base_event["properties"]["nodeId"], "EFR-v3-second"]
    result["edges"] = [e for e in result["edges"] if e["type"] != "COVERS"]
    for index, event_id in enumerate(event_ids):
        result["edges"].append({
            "edgeId": f"edge_covers_{index}",
            "type": "COVERS",
            "startNodeId": article_ai_id,
            "endNodeId": event_id,
            "properties": {"isPrimary": index == primary_index},
        })
    result["edges"].append({
        "edgeId": "edge_causes_0",
        "type": "CAUSES",
        "startNodeId": event_ids[0],
        "endNodeId": event_ids[1],
        "properties": {},
    })
    monkeypatch.setattr(service, "_call_ai", lambda request: result)

    response = client.post(
        "/internal/v1/articles/analyze",
        json={
            "articleId": test_article_id,
            "title": "서울시, 청년 주거 지원 확대",
            "content": "목업 대체",
            "sourceId": test_source_id,
            "sourceName": "테스트뉴스",
            "publishedAt": "2026-09-08T09:00:00+09:00",
        },
        headers={"x-internal-api-key": settings.internal_api_key},
    )
    assert response.status_code == 200
    article_node_id = response.json()["data"]["articleNodeId"]

    with _driver.session() as session:
        record = session.run(
            """
            MATCH (a:Article {nodeId: $articleId})-[c:COVERS]->(ev:Event)
            WITH a, collect(CASE WHEN c.isPrimary = true THEN ev.title END) AS primaryTitles,
                 count(ev) AS eventCount
            OPTIONAL MATCH (a)-[:COVERS]->(:Event)-[causes:CAUSES]->(:Event)
            RETURN primaryTitles, eventCount, count(causes) AS causesCount
            """,
            articleId=article_node_id,
        ).single()

    expected_title = (base_event if primary_index == 0 else second_event)["properties"]["title"]
    assert record["eventCount"] == 2
    assert record["primaryTitles"] == [expected_title]
    assert record["causesCount"] == 1
