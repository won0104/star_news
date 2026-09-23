from datetime import datetime, timedelta, timezone

from app.database import _driver
from app.recommendations import service
from app.recommendations.schemas import RecommendationCalculateRequest, UserRecommendationRequest

# NORMAL_USER는 SIMILAR_USER와 공통 소비(CF 재료) + 비슷한 임베딩(CBF 재료)이 있어 개인화(NORMAL) 결과가 나와야 함.
# SIMILAR_USER는 관심Topic 안/밖, 비선호Topic 이벤트를 각각 소비해서 하드 필터가 실제로 걸리는지 같이 검증한다.
# COLD_START_USER는 CONSUMED 이력이 전혀 없어 인기도 폴백(COLD_START)으로 빠져야 함.
NORMAL_USER_ID = 8501
SIMILAR_USER_ID = 8502
COLD_START_USER_ID = 8503
NONEXISTENT_USER_ID = 8599
EMBEDDING_DIMENSIONS = 1024


def _unit_vector(index: int) -> list[float]:
    vector = [0.0] * EMBEDDING_DIMENSIONS
    vector[index] = 1.0
    return vector


# 이전 실행에서 남은 테스트 유저/Event/Topic을 지워서 재실행해도 항상 같은 결과가 나오게 함
def _reset_fixture(session):
    session.run(
        "MATCH (u:User) WHERE u.userId IN $userIds DETACH DELETE u",
        userIds=[NORMAL_USER_ID, SIMILAR_USER_ID, COLD_START_USER_ID, NONEXISTENT_USER_ID],
    )
    session.run("MATCH (e:Event) WHERE e.nodeId STARTS WITH 'test-calc-event-' DETACH DELETE e")
    session.run("MATCH (t:Topic) WHERE t.topicCode IN ['TEST_CALC_TOPIC', 'TEST_CALC_DISLIKED'] DETACH DELETE t")


# NORMAL_USER의 관심Topic/비선호Topic까지 포함해서, CF/CBF 하드 필터가 실제로 걸리는지 검증할 수 있는 재료를 만든다
def _seed_fixture(session):
    now = datetime.now(timezone.utc)
    recent = now - timedelta(hours=1)

    session.run(
        """
        MERGE (target:User {userId: $targetUserId})
        MERGE (similar:User {userId: $similarUserId})
        MERGE (coldUser:User {userId: $coldStartUserId})
        MERGE (topic:Topic {topicCode: 'TEST_CALC_TOPIC'})
        MERGE (disliked:Topic {topicCode: 'TEST_CALC_DISLIKED'})
        MERGE (target)-[:INTERESTED_IN]->(topic)
        MERGE (target)-[:DISLIKES]->(disliked)

        // target과 similar가 공통 소비 -> CF 재료. 임베딩도 있어서 CBF 프로필 벡터 재료도 됨
        MERGE (consumed:Event {nodeId: 'test-calc-event-consumed'})
        SET consumed.embedding = $vector, consumed.occurredAt = $recent, consumed.title = '이미 읽은 이벤트'
        MERGE (target)-[r1:CONSUMED]->(consumed)
        SET r1.eventClickCount = 1, r1.lastViewedAt = $recent
        MERGE (similar)-[r2:CONSUMED]->(consumed)
        SET r2.eventClickCount = 1, r2.lastViewedAt = $recent

        // similar만 소비 + 임베딩 비슷함 + 관심 Topic 안 -> target의 최종 추천 후보가 되어야 함
        // :PrimaryEvent도 같이 붙임 - CF/CBF/콜드스타트 후보 조회가 이제 이 라벨을 요구함
        MERGE (rec:Event:PrimaryEvent {nodeId: 'test-calc-event-recommend'})
        SET rec.embedding = $vector, rec.occurredAt = $recent, rec.title = '추천될 이벤트'
        MERGE (rec)-[:CLASSIFIED_AS]->(topic)
        MERGE (similar)-[:CONSUMED]->(rec)

        // similar만 소비 + 임베딩 비슷함 + 관심 Topic 밖 -> 관심 Topic 하드 필터에 걸려서 추천되면 안 됨
        MERGE (outside:Event:PrimaryEvent {nodeId: 'test-calc-event-outside-topic'})
        SET outside.embedding = $vector, outside.occurredAt = $recent, outside.title = 'Topic 밖 이벤트'
        MERGE (similar)-[:CONSUMED]->(outside)

        // similar만 소비 + 임베딩 비슷함 + 비선호 Topic -> 비선호 필터에 걸려서 추천되면 안 됨
        MERGE (dislikedEvent:Event:PrimaryEvent {nodeId: 'test-calc-event-disliked'})
        SET dislikedEvent.embedding = $vector, dislikedEvent.occurredAt = $recent, dislikedEvent.title = '비선호 이벤트'
        MERGE (dislikedEvent)-[:CLASSIFIED_AS]->(disliked)
        MERGE (similar)-[:CONSUMED]->(dislikedEvent)

        // 콜드스타트 유저용 인기 Event (소비자 1명 있어야 인기도 > 0)
        MERGE (popular:Event:PrimaryEvent {nodeId: 'test-calc-event-popular'})
        SET popular.occurredAt = $recent, popular.title = '인기 이벤트'
        MERGE (popular)-[:CLASSIFIED_AS]->(topic)
        MERGE (similar)-[:CONSUMED]->(popular)
        """,
        targetUserId=NORMAL_USER_ID,
        similarUserId=SIMILAR_USER_ID,
        coldStartUserId=COLD_START_USER_ID,
        vector=_unit_vector(0),
        recent=recent,
    )


# 존재하지 않는 유저는 결과에서 빠지고, 존재하는 유저는 정상 처리되는지 확인 (부분 성공)
def test_calculate_recommendations_skips_nonexistent_user_and_returns_others():
    with _driver.session() as session:
        _reset_fixture(session)
        _seed_fixture(session)
        request = RecommendationCalculateRequest(
            cycle="AM",
            users=[
                UserRecommendationRequest(user_id=NORMAL_USER_ID, limit=10),
                UserRecommendationRequest(user_id=NONEXISTENT_USER_ID, limit=10),
            ],
        )
        response = service.calculate_recommendations(request, session)

    result_user_ids = {r.user_id for r in response.results}
    assert NONEXISTENT_USER_ID not in result_user_ids
    assert NORMAL_USER_ID in result_user_ids
    assert response.cycle == "AM"


# 소비 이력이 있는 유저는 NORMAL 타입으로, 관심 Topic 밖/비선호 Topic Event는 제외되고
# label/topicCode가 채워지고 rank가 1부터 매겨지는지 확인
def test_calculate_recommendations_marks_normal_type_and_applies_hard_filters():
    with _driver.session() as session:
        _reset_fixture(session)
        _seed_fixture(session)
        request = RecommendationCalculateRequest(
            cycle="PM",
            users=[UserRecommendationRequest(user_id=NORMAL_USER_ID, limit=10)],
        )
        response = service.calculate_recommendations(request, session)

    result = next(r for r in response.results if r.user_id == NORMAL_USER_ID)
    item_by_id = {item.event_id: item for item in result.items}

    # 이미 소비한 Event, 관심 Topic 밖 Event, 비선호 Topic Event는 추천 후보에서 빠져야 함
    assert "test-calc-event-consumed" not in item_by_id
    assert "test-calc-event-outside-topic" not in item_by_id
    assert "test-calc-event-disliked" not in item_by_id

    recommended = item_by_id["test-calc-event-recommend"]
    assert recommended.recommendation_type == "NORMAL"
    assert recommended.label == "추천될 이벤트"
    assert recommended.topic_code == "TEST_CALC_TOPIC"
    assert all(item.rank == i + 1 for i, item in enumerate(result.items))


# 소비 이력이 없는 유저는 COLD_START 타입(인기도 폴백)으로 처리되는지 확인
def test_calculate_recommendations_marks_cold_start_type_for_user_without_history():
    with _driver.session() as session:
        _reset_fixture(session)
        _seed_fixture(session)
        request = RecommendationCalculateRequest(
            cycle="AM",
            users=[UserRecommendationRequest(user_id=COLD_START_USER_ID, limit=10)],
        )
        response = service.calculate_recommendations(request, session)

    result = next(r for r in response.results if r.user_id == COLD_START_USER_ID)
    assert len(result.items) >= 1
    assert all(item.recommendation_type == "COLD_START" for item in result.items)
