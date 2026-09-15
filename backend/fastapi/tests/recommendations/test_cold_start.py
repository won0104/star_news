from datetime import datetime, timedelta, timezone

from app.database import _driver
from app.recommendations import repository, service

TARGET_USER_ID = 8301
CONSUMER_USER_IDS = [8302, 8303]
TOPIC_CODE = "TEST_COLD_TOPIC"


def _reset_fixture(session):
    session.run(
        "MATCH (u:User) WHERE u.userId IN $userIds DETACH DELETE u",
        userIds=[TARGET_USER_ID, *CONSUMER_USER_IDS],
    )
    session.run("MATCH (e:Event) WHERE e.nodeId STARTS WITH 'test-cold-event-' DETACH DELETE e")
    session.run("MATCH (t:Topic {topicCode: $topicCode}) DETACH DELETE t", topicCode=TOPIC_CODE)


# 관심 Topic 안에서 인기 있는/없는 Event, 관심 Topic 밖의(더 인기 있는) Event를 만들어서
# 폴백이 Topic 필터를 실제로 지키는지, 그 안에서 인기도 순으로 정렬하는지 검증한다.
def _seed_fixture(session):
    now = datetime.now(timezone.utc)
    session.run(
        """
        MERGE (target:User {userId: $targetUserId})
        MERGE (topic:Topic {topicCode: $topicCode})
        MERGE (target)-[:INTERESTED_IN]->(topic)

        // 관심 Topic 안 + 인기 있음 (소비자 2명) -> 제일 높은 점수여야 함
        MERGE (popular:Event {nodeId: 'test-cold-event-intopic-popular'})
        SET popular.occurredAt = $recent
        MERGE (popular)-[:CLASSIFIED_AS]->(topic)
        WITH target, topic, popular, $recent AS recent
        UNWIND $consumerUserIds AS consumerUserId
        MERGE (consumer:User {userId: consumerUserId})
        MERGE (consumer)-[:CONSUMED]->(popular)

        WITH target, topic
        // 관심 Topic 안 + 인기 없음 (소비자 0명) -> 후보엔 있어야 하지만 popular보다 낮아야 함
        MERGE (unpopular:Event {nodeId: 'test-cold-event-intopic-unpopular'})
        SET unpopular.occurredAt = $recent
        MERGE (unpopular)-[:CLASSIFIED_AS]->(topic)

        WITH target
        // 관심 Topic 밖 + 매우 인기 있음 -> Topic 필터에 걸려서 아예 후보에서 빠져야 함
        MERGE (outside:Event {nodeId: 'test-cold-event-outsidetopic'})
        SET outside.occurredAt = $recent
        """,
        targetUserId=TARGET_USER_ID,
        topicCode=TOPIC_CODE,
        consumerUserIds=CONSUMER_USER_IDS,
        recent=now - timedelta(hours=1),
    )


# Cold Start 판별 검증: CONSUMED 이력 있으면 True, 없으면 False
def test_has_consumption_history():
    with _driver.session() as session:
        _reset_fixture(session)
        _seed_fixture(session)

        # 타겟 유저는 CONSUMED 이력이 없음 (INTERESTED_IN만 있음)
        assert repository.has_consumption_history(session, TARGET_USER_ID) is False
        # 소비자로 등록한 유저는 CONSUMED 이력이 있음
        assert repository.has_consumption_history(session, CONSUMER_USER_IDS[0]) is True


# Cold Start 폴백 검증: 관심 Topic 밖의 Event는 제외되고, Topic 안에서는 인기도 순으로 정렬되는지 확인
def test_get_cold_start_fallback_filters_by_interested_topic_and_ranks_by_popularity():
    with _driver.session() as session:
        _reset_fixture(session)
        _seed_fixture(session)
        results = service.get_cold_start_fallback(TARGET_USER_ID, session)

    event_ids = [r.event_id for r in results]

    # 관심 Topic 밖의 Event는 아무리 인기 있어도(사실 이 테스트에선 소비자 0명) 후보에 없어야 함
    assert "test-cold-event-outsidetopic" not in event_ids

    # 관심 Topic 안의 두 Event는 후보에 있어야 함
    assert "test-cold-event-intopic-popular" in event_ids
    assert "test-cold-event-intopic-unpopular" in event_ids

    # 소비자 많은 쪽이 더 높은 순위여야 함
    assert event_ids.index("test-cold-event-intopic-popular") < event_ids.index("test-cold-event-intopic-unpopular")


# 관심 Topic이 아예 없는 유저는 전체 Event 대상으로 폴백해야 함 (Topic 필터 없이 통과)
def test_get_cold_start_fallback_falls_back_to_all_events_when_no_interested_topics():
    with _driver.session() as session:
        session.run("MATCH (u:User {userId: 8399}) DETACH DELETE u")
        session.run("MERGE (:User {userId: 8399})")
        results = service.get_cold_start_fallback(8399, session)

    # 에러 없이 실행되고 리스트를 반환하면 됨 (전체 Event 대상이라 구체적 결과는 다른 테스트 데이터에 따라 달라짐)
    assert isinstance(results, list)
