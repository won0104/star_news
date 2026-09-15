from fastapi.testclient import TestClient

from app.config import settings
from app.database import _driver
from app.main import app

client = TestClient(app)


# /user-graph/sync 엔드포인트 검증. 로컬 Neo4j(스키마 제약조건만 있으면 충분, mock 데이터 불필요)를 전제로 한다.
def test_sync_user_graph_creates_user_and_relationships():
    # 0) 이전 실행에서 남은 테스트 사용자를 지워서 stale 체크(409)에 안 걸리게 함 (재실행 가능하게)
    with _driver.session() as session:
        session.run("MATCH (u:User {userId: 9999}) DETACH DELETE u")

    # 1) 테스트에 필요한 최소 데이터를 직접 만듦 (mock 데이터가 이미 있어도 MERGE라 중복 안 생김)
    with _driver.session() as session:
        session.run("MERGE (t:Topic {topicCode: 'ECONOMY'}) ON CREATE SET t.nodeId = 'test-topic-economy'")
        session.run("MERGE (t:Topic {topicCode: 'SPORTS'}) ON CREATE SET t.nodeId = 'test-topic-sports'")
        session.run("MERGE (:Event {nodeId: 'test-event-1'})")
        session.run("MERGE (:Event {nodeId: 'test-event-2'})")
        topic_id = session.run("MATCH (t:Topic {topicCode: 'ECONOMY'}) RETURN t.nodeId AS id").single()["id"]
        event_ids = ["test-event-1", "test-event-2"]

    # 새 사용자(9999)가 ECONOMY에 관심, SPORTS는 비선호, Event 2개를 소비했다고 가정한 요청
    payload = {
        "users": [
            {
                "userId": 9999,
                "interestNodes": [{"nodeType": "TOPIC", "nodeKey": topic_id}],
                "dislikeTopicCodes": ["SPORTS"],
                "consumedEvents": [
                    {
                        "eventId": event_ids[0],
                        "eventClickCount": 2,
                        "lastViewedAt": "2024-05-25T05:30:00+09:00",
                        "eventFavorited": True,
                    },
                    {
                        "eventId": event_ids[1],
                        "eventClickCount": 1,
                        "lastViewedAt": "2024-05-25T05:31:00+09:00",
                        "eventFavorited": False,
                    },
                ],
            }
        ],
        "aggregatedAt": "2024-05-25T05:40:00+09:00",
    }

    # 2) 실제 엔드포인트 호출 및 응답 확인
    response = client.post(
        "/internal/v1/user-graph/sync",
        json=payload,
        headers={"x-internal-api-key": settings.internal_api_key},
    )

    assert response.status_code == 200
    assert response.json()["data"]["processedUsers"] == 1

    # 3) API 응답만 믿지 않고, 실제 Neo4j에 관계가 반영됐는지 직접 확인
    with _driver.session() as session:
        record = session.run(
            """
            MATCH (u:User {userId: 9999})
            OPTIONAL MATCH (u)-[:INTERESTED_IN]->(it:Topic)
            OPTIONAL MATCH (u)-[:DISLIKES]->(dt:Topic)
            OPTIONAL MATCH (u)-[:CONSUMED]->(ce:Event)
            RETURN count(DISTINCT it) AS interestCount,
                   count(DISTINCT dt) AS dislikeCount,
                   count(DISTINCT ce) AS consumedCount
            """
        ).single()

    assert record["interestCount"] == 1
    assert record["dislikeCount"] == 1
    assert record["consumedCount"] == 2


# 배치 안 유저 한 명이 실패해도(존재하지 않는 Event 참조) 나머지 유저는 격리되어 정상 처리되는지 검증
def test_sync_user_graph_isolates_failure_and_keeps_processing_other_users():
    with _driver.session() as session:
        session.run("MATCH (u:User) WHERE u.userId IN [9998, 9997] DETACH DELETE u")
        session.run("MERGE (:Event {nodeId: 'test-event-isolation'})")

    payload = {
        "users": [
            # 정상 유저 - 실제 존재하는 Event를 소비
            {
                "userId": 9998,
                "interestNodes": [],
                "dislikeTopicCodes": [],
                "consumedEvents": [
                    {
                        "eventId": "test-event-isolation",
                        "eventClickCount": 1,
                        "lastViewedAt": "2024-05-25T05:30:00+09:00",
                    }
                ],
            },
            # 실패 유저 - Neo4j에 없는 Event를 참조 (배치 중간에 있어서, 얘 때문에 뒤에 오는 유저가 막히면 안 됨)
            {
                "userId": 9997,
                "interestNodes": [],
                "dislikeTopicCodes": [],
                "consumedEvents": [
                    {
                        "eventId": "test-event-does-not-exist",
                        "eventClickCount": 1,
                        "lastViewedAt": "2024-05-25T05:30:00+09:00",
                    }
                ],
            },
        ],
        "aggregatedAt": "2024-05-25T05:40:00+09:00",
    }

    response = client.post(
        "/internal/v1/user-graph/sync",
        json=payload,
        headers={"x-internal-api-key": settings.internal_api_key},
    )

    # 유저 하나가 실패해도 전체 응답은 200 - 예전처럼 요청 전체가 404로 끊기지 않음
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["processedUsers"] == 2
    assert data["updatedUsers"] == 1
    assert data["failed"] == [{"userId": 9997, "code": "GRAPH_REFERENCE_NOT_FOUND"}]

    # 정상 유저(9998)는 실제로 Neo4j에 반영됐는지 확인
    with _driver.session() as session:
        consumed_count = session.run(
            "MATCH (:User {userId: 9998})-[:CONSUMED]->(:Event) RETURN count(*) AS c"
        ).single()["c"]
    assert consumed_count == 1
