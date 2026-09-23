import pytest

from app.database import _driver
from app.recommendations import repository, service

# 8001(본인), 8002(overlap 2 -> jaccard 2/3), 8003(overlap 1 -> jaccard 1/5)로
# 겹치는 정도가 다른 유사 유저를 만들어서 Jaccard 계산과 정렬이 맞는지 검증한다.
TARGET_USER_ID = 8001
SIMILAR_USER_HIGH_ID = 8002
SIMILAR_USER_LOW_ID = 8003


# 이전 실행에서 남은 테스트 유저/Event를 지워서 재실행해도 항상 같은 결과가 나오게 함
def _reset_fixture(session):
    session.run(
        "MATCH (u:User) WHERE u.userId IN $userIds DETACH DELETE u",
        userIds=[TARGET_USER_ID, SIMILAR_USER_HIGH_ID, SIMILAR_USER_LOW_ID, 9998],
    )
    session.run("MATCH (e:Event) WHERE e.nodeId STARTS WITH 'test-cf-event-' DETACH DELETE e")


# 유사도가 다른 두 유저(High/Low)를 만들어 Jaccard 순위가 제대로 갈리는지 검증할 수 있게 함
def _seed_fixture(session):
    # 본인: event-a, event-b 소비
    # :PrimaryEvent도 같이 붙임 - CF 후보 조회가 이제 이 라벨을 요구함(적어도 한 기사에서 메인 주제였던 적 있는 Event만 후보)
    session.run(
        """
        MERGE (u:User {userId: $userId})
        MERGE (a:Event:PrimaryEvent {nodeId: 'test-cf-event-a'})
        MERGE (b:Event:PrimaryEvent {nodeId: 'test-cf-event-b'})
        MERGE (u)-[:CONSUMED]->(a)
        MERGE (u)-[:CONSUMED]->(b)
        """,
        userId=TARGET_USER_ID,
    )
    # 유사도 높은 유저: event-a, event-b, event-c 소비 (overlap 2, 전체 3 -> jaccard 2/3)
    session.run(
        """
        MERGE (u:User {userId: $userId})
        MERGE (a:Event:PrimaryEvent {nodeId: 'test-cf-event-a'})
        MERGE (b:Event:PrimaryEvent {nodeId: 'test-cf-event-b'})
        MERGE (c:Event:PrimaryEvent {nodeId: 'test-cf-event-c'})
        MERGE (u)-[:CONSUMED]->(a)
        MERGE (u)-[:CONSUMED]->(b)
        MERGE (u)-[:CONSUMED]->(c)
        """,
        userId=SIMILAR_USER_HIGH_ID,
    )
    # 유사도 낮은 유저: event-a, event-d, event-e, event-f 소비 (overlap 1, 전체 4 -> jaccard 1/5)
    session.run(
        """
        MERGE (u:User {userId: $userId})
        MERGE (a:Event:PrimaryEvent {nodeId: 'test-cf-event-a'})
        MERGE (d:Event:PrimaryEvent {nodeId: 'test-cf-event-d'})
        MERGE (e:Event:PrimaryEvent {nodeId: 'test-cf-event-e'})
        MERGE (f:Event:PrimaryEvent {nodeId: 'test-cf-event-f'})
        MERGE (u)-[:CONSUMED]->(a)
        MERGE (u)-[:CONSUMED]->(d)
        MERGE (u)-[:CONSUMED]->(e)
        MERGE (u)-[:CONSUMED]->(f)
        """,
        userId=SIMILAR_USER_LOW_ID,
    )


# repository 레벨 검증: Jaccard 유사도 계산 자체가 맞는지, 이미 본인이 본 Event는 제외되는지 확인
def test_find_cf_candidate_events_ranks_by_jaccard_similarity():
    with _driver.session() as session:
        _reset_fixture(session)
        _seed_fixture(session)
        candidates = repository.find_cf_candidate_events(session, TARGET_USER_ID)

    by_event_id = {c["eventId"]: c["cfScore"] for c in candidates}

    # 이미 본인이 소비한 event-a, event-b는 후보에서 제외되어야 함
    assert "test-cf-event-a" not in by_event_id
    assert "test-cf-event-b" not in by_event_id

    # 유사도 높은 유저(jaccard 2/3)가 준 event-c가 가장 높은 점수
    assert by_event_id["test-cf-event-c"] == pytest.approx(2 / 3)
    # 유사도 낮은 유저(jaccard 1/5)가 준 event-d/e/f는 더 낮은 동일 점수
    assert by_event_id["test-cf-event-d"] == pytest.approx(1 / 5)
    assert by_event_id["test-cf-event-e"] == pytest.approx(1 / 5)
    assert by_event_id["test-cf-event-f"] == pytest.approx(1 / 5)

    # cfScore 내림차순 정렬 확인
    assert candidates[0]["eventId"] == "test-cf-event-c"


# service 레벨 검증: repository의 dict 결과를 CFCandidate 스키마로 잘 감싸서 반환하는지 확인
def test_calculate_cf_scores_wraps_repository_result_as_cf_candidate():
    with _driver.session() as session:
        _reset_fixture(session)
        _seed_fixture(session)
        scores = service.calculate_cf_scores(TARGET_USER_ID, session)

    assert {score.event_id for score in scores} == {
        "test-cf-event-c",
        "test-cf-event-d",
        "test-cf-event-e",
        "test-cf-event-f",
    }


# Cold Start 검증: CONSUMED 이력이 없어도 에러 없이 빈 리스트를 반환하는지 확인
def test_calculate_cf_scores_returns_empty_list_when_no_consumed_history():
    with _driver.session() as session:
        session.run("MATCH (u:User {userId: 9998}) DETACH DELETE u")
        session.run("MERGE (:User {userId: 9998})")
        scores = service.calculate_cf_scores(9998, session)

    assert scores == []
