from datetime import datetime, timedelta, timezone

from app.database import _driver
from app.recommendations import service

USER_ID = 8201
EMBEDDING_DIMENSIONS = 768


# 특정 인덱스만 1.0이고 나머지는 0인 단위벡터 (서로 직교 -> 코사인 유사도 0)
def _unit_vector(index: int) -> list[float]:
    vector = [0.0] * EMBEDDING_DIMENSIONS
    vector[index] = 1.0
    return vector


# 기준 벡터랑 방향은 비슷하지만 살짝 다른 벡터 (코사인 유사도가 1은 아니지만 높게 나옴)
def _near_vector(index: int, noise_index: int) -> list[float]:
    vector = _unit_vector(index)
    vector[noise_index] = 0.3
    return vector


# 순수 계산 로직 검증: Neo4j 없이 가중평균 공식 자체가 맞는지 확인 (사람이 직접 계산한 값과 대조)
def test_build_user_profile_vector_computes_weighted_average():
    now = datetime.now(timezone.utc)
    consumed_events = [
        # 최근 + 많이 본 Event -> 가중치가 커서 프로필 벡터에 크게 반영돼야 함
        {"embedding": [0.2, 0.5, 0.1, 0.3, 0.0, 0.4, 0.2, 0.1], "count": 5, "lastViewedAt": now},
        # 90일 전 + 1번만 본 Event -> 가중치가 작아 거의 영향 없어야 함
        {"embedding": [0.1, 0.3, 0.4, 0.0, 0.2, 0.1, 0.3, 0.5], "count": 1, "lastViewedAt": now - timedelta(days=90)},
    ]

    profile_vector = service._build_user_profile_vector(consumed_events)

    # 두 Event의 가중치 차이를 감안했을 때 나와야 할 예상 범위 (손계산 값과 대조)
    assert profile_vector[0] > 0.15
    assert profile_vector[0] < 0.2
    assert len(profile_vector) == 8 # 원본 임베딩과 같은 차원 수를 유지해야 함


# Cold Start 검증: CONSUMED 이력이 없으면 벡터를 만들 수 없으니 None 반환
def test_build_user_profile_vector_returns_none_when_no_history():
    assert service._build_user_profile_vector([]) is None

# 이전 테스트 실행에서 남은 데이터 정리 (재실행 시 누적 방지)
def _reset_fixture(session):
    session.run("MATCH (u:User {userId: $userId}) DETACH DELETE u", userId=USER_ID)
    session.run("MATCH (e:Event) WHERE e.nodeId STARTS WITH 'test-cbf-event-' DETACH DELETE e")


def _seed_fixture(session):
    now = datetime.now(timezone.utc)
    session.run(
        """
        MERGE (u:User {userId: $userId})

        // 본인이 이미 소비한 Event - 이 임베딩으로 취향 벡터가 만들어짐
        MERGE (consumed:Event {nodeId: 'test-cbf-event-consumed'})
        SET consumed.embedding = $consumedVector
        MERGE (u)-[r:CONSUMED]->(consumed)
        SET r.count = 3, r.lastViewedAt = $now

        // 취향 벡터랑 방향이 비슷한 미열람 Event -> 유사도 높게 나와야 함
        MERGE (similar:Event {nodeId: 'test-cbf-event-similar'})
        SET similar.embedding = $similarVector

        // 취향 벡터랑 직교하는 미열람 Event -> 유사도 낮게 나와야 함
        MERGE (dissimilar:Event {nodeId: 'test-cbf-event-dissimilar'})
        SET dissimilar.embedding = $dissimilarVector
        """,
        userId=USER_ID,
        consumedVector=_unit_vector(0),
        similarVector=_near_vector(0, 1),
        dissimilarVector=_unit_vector(767),
        now=now,
    )


# 통합 테스트: 프로필 벡터 계산 -> Vector 인덱스 검색 -> 필터링까지
def test_calculate_cbf_scores_ranks_similar_event_higher():
    with _driver.session() as session:
        _reset_fixture(session)
        _seed_fixture(session)
        scores = service.calculate_cbf_scores(USER_ID, session)

    by_event_id = {s.event_id: s.content_score for s in scores}

    # 이미 소비한 Event는 후보에서 제외되어야 함
    assert "test-cbf-event-consumed" not in by_event_id

    # 취향 벡터랑 비슷한 Event가 후보에 있어야 하고, 무관한 Event보다 점수가 높아야 함
    assert "test-cbf-event-similar" in by_event_id

    # 유사한 게 무관한 것보다 점수가 높아야 함
    if "test-cbf-event-dissimilar" in by_event_id:
        assert by_event_id["test-cbf-event-similar"] > by_event_id["test-cbf-event-dissimilar"]


# Cold Start 통합 검증: 소비 이력 없는 유저는 에러 없이 빈 리스트를 받아야 함
def test_calculate_cbf_scores_returns_empty_list_when_no_consumed_history():
    with _driver.session() as session:
        session.run("MATCH (u:User {userId: 9997}) DETACH DELETE u")
        session.run("MERGE (:User {userId: 9997})")
        scores = service.calculate_cbf_scores(9997, session)

    assert scores == []
