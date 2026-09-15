from datetime import datetime, timedelta, timezone

from app.database import _driver
from app.recommendations import repository, service

# 미열람/비선호 Topic/최근성 3개 필터가 각각 하나의 이유로 후보에서 빠지는 Event를 만들어서
# 실제로 통과하는 건 조건을 다 만족하는 test-filter-event-valid 하나뿐인지 검증한다.
USER_ID = 8101


# 이전 실행에서 남은 테스트 유저/Event/Topic을 지워서 재실행해도 항상 같은 결과가 나오게 함
def _reset_fixture(session):
    session.run("MATCH (u:User {userId: $userId}) DETACH DELETE u", userId=USER_ID)
    session.run("MATCH (e:Event) WHERE e.nodeId STARTS WITH 'test-filter-event-' DETACH DELETE e")
    session.run("MATCH (t:Topic {topicCode: 'TEST_DISLIKED_TOPIC'}) DETACH DELETE t")


# 필터별로 정확히 하나씩 걸릴 이유가 있는 Event를 만들어서, 3개 필터가 각자 제 역할을 하는지 구분해서 볼 수 있게 함
def _seed_fixture(session):
    now = datetime.now(timezone.utc)
    recent = now - timedelta(days=1)
    too_old = now - timedelta(days=repository.RECENCY_WINDOW_DAYS + 1)

    session.run(
        """
        MERGE (u:User {userId: $userId})
        MERGE (disliked:Topic {topicCode: 'TEST_DISLIKED_TOPIC'})
        MERGE (u)-[:DISLIKES]->(disliked)

        // 미열람 필터에 걸려야 함: 본인이 이미 소비함
        MERGE (consumed:Event {nodeId: 'test-filter-event-consumed'})
        SET consumed.occurredAt = $recent
        MERGE (u)-[:CONSUMED]->(consumed)

        // 비선호 Topic 필터에 걸려야 함: 비선호 Topic으로 분류됨
        MERGE (dislikedEvent:Event {nodeId: 'test-filter-event-disliked'})
        SET dislikedEvent.occurredAt = $recent
        MERGE (dislikedEvent)-[:CLASSIFIED_AS]->(disliked)

        // 최근성 필터에 걸려야 함: 기간 밖
        MERGE (oldEvent:Event {nodeId: 'test-filter-event-old'})
        SET oldEvent.occurredAt = $tooOld

        // 세 필터 다 통과해야 함
        MERGE (validEvent:Event {nodeId: 'test-filter-event-valid'})
        SET validEvent.occurredAt = $recent
        """,
        userId=USER_ID,
        recent=recent,
        tooOld=too_old,
    )


# 3개 필터(미열람/비선호 Topic/최근성)를 각각 하나씩 위반하는 Event는 빠지고, 다 통과하는 Event만 남는지 확인
def test_get_eligible_candidate_event_ids_applies_all_filters():
    with _driver.session() as session:
        _reset_fixture(session)
        _seed_fixture(session)
        eligible = service.get_eligible_candidate_event_ids(USER_ID, session)

    assert "test-filter-event-valid" in eligible
    assert "test-filter-event-consumed" not in eligible
    assert "test-filter-event-disliked" not in eligible
    assert "test-filter-event-old" not in eligible
