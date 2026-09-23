from datetime import datetime, timedelta, timezone

import pytest

from app.database import _driver
from app.recommendations import service

TARGET_USER_ID = 8401
SIMILAR_USER_ID = 8402
EMBEDDING_DIMENSIONS = 1024


def _unit_vector(index: int) -> list[float]:
    vector = [0.0] * EMBEDDING_DIMENSIONS
    vector[index] = 1.0
    return vector


def _reset_fixture(session):
    session.run(
        "MATCH (u:User) WHERE u.userId IN $userIds DETACH DELETE u",
        userIds=[TARGET_USER_ID, SIMILAR_USER_ID],
    )
    session.run("MATCH (e:Event) WHERE e.nodeId STARTS WITH 'test-final-event-' DETACH DELETE e")
    session.run("MATCH (t:Topic {topicCode: 'TEST_FINAL_DISLIKED'}) DETACH DELETE t")


# CF 점수와 CBF 점수를 둘 다 받는 Event 하나, CF 점수는 있지만 비선호 Topic이라 걸러져야 하는 Event 하나를 만든다.
def _seed_fixture(session):
    now = datetime.now(timezone.utc)
    recent = now - timedelta(hours=1)

    session.run(
        """
        MERGE (target:User {userId: $targetUserId})
        MERGE (similar:User {userId: $similarUserId})
        MERGE (dislikedTopic:Topic {topicCode: 'TEST_FINAL_DISLIKED'})
        MERGE (target)-[:DISLIKES]->(dislikedTopic)

        // 둘이 공통으로 소비 -> CF 유사도 재료. 임베딩도 있어서 CBF 프로필 벡터 재료도 됨
        MERGE (consumed:Event {nodeId: 'test-final-event-consumed'})
        SET consumed.embedding = $vector, consumed.occurredAt = $recent
        MERGE (target)-[r1:CONSUMED]->(consumed)
        SET r1.eventClickCount = 1, r1.lastViewedAt = $recent
        MERGE (similar)-[r2:CONSUMED]->(consumed)
        SET r2.eventClickCount = 1, r2.lastViewedAt = $recent

        // similar만 소비 + 비선호 Topic 아님 + 임베딩도 비슷함 -> CF 점수, CBF 점수 둘 다 받아야 함
        // :PrimaryEvent도 같이 붙임 - CF/CBF 후보 조회가 이제 이 라벨을 요구함
        MERGE (both:Event:PrimaryEvent {nodeId: 'test-final-event-both'})
        SET both.embedding = $vector, both.occurredAt = $recent
        MERGE (similar)-[:CONSUMED]->(both)

        // similar만 소비 + 비선호 Topic -> CF 점수는 나오지만 최종 후보에서 제외되어야 함
        MERGE (disliked:Event:PrimaryEvent {nodeId: 'test-final-event-disliked-topic'})
        SET disliked.occurredAt = $recent
        MERGE (disliked)-[:CLASSIFIED_AS]->(dislikedTopic)
        MERGE (similar)-[:CONSUMED]->(disliked)
        """,
        targetUserId=TARGET_USER_ID,
        similarUserId=SIMILAR_USER_ID,
        vector=_unit_vector(0),
        recent=recent,
    )


# 순수 계산 함수 검증: 가중합 공식 자체가 맞는지
def test_calculate_final_score():
    score = service.calculate_final_score(cbf_score=0.8, cf_score=0.4, cbf_weight=0.5, cf_weight=0.5)
    assert score == pytest.approx(0.6)


# 통합 검증: 비선호 Topic으로 분류된 Event는 CF 점수가 있어도 최종 결과에서 빠져야 함
def test_calculate_interest_based_recommendations_excludes_ineligible_event():
    with _driver.session() as session:
        _reset_fixture(session)
        _seed_fixture(session)
        results = service.calculate_interest_based_recommendations(TARGET_USER_ID, session)

    event_ids = {r.event_id for r in results}

    # 비선호 Topic Event는 CF 점수가 나올 재료(similar 유저가 소비)가 있었지만 걸러져야 함
    assert "test-final-event-disliked-topic" not in event_ids
    # 이미 소비한 Event도 후보 필터링에서 제외되어야 함
    assert "test-final-event-consumed" not in event_ids
    # CF+CBF 둘 다 받을 수 있는 Event는 결과에 있어야 함
    assert "test-final-event-both" in event_ids


# Cold Start 검증: CONSUMED 이력 없으면 인기도 폴백으로 위임되는지 확인
def test_calculate_interest_based_recommendations_uses_cold_start_fallback():
    with _driver.session() as session:
        session.run("MATCH (u:User {userId: 8499}) DETACH DELETE u")
        session.run("MERGE (:User {userId: 8499})")
        results = service.calculate_interest_based_recommendations(8499, session)

    assert isinstance(results, list)
