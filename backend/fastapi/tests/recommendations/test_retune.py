from datetime import datetime, timedelta, timezone

from app.database import _driver
from app.recommendations import service

# 최소 평가 조건(이력 2개 이상)만 채우는 간단한 유저 - 홀드아웃 안전성/그리드서치 동작만 확인하면 되므로
EVAL_USER_ID = 8601
EMBEDDING_DIMENSIONS = 1024


def _unit_vector(index: int) -> list[float]:
    vector = [0.0] * EMBEDDING_DIMENSIONS
    vector[index] = 1.0
    return vector


def _reset_fixture(session):
    session.run("MATCH (u:User) WHERE u.userId = $userId DETACH DELETE u", userId=EVAL_USER_ID)
    session.run("MATCH (e:Event) WHERE e.nodeId STARTS WITH 'test-retune-event-' DETACH DELETE e")


def _seed_fixture(session):
    recent = datetime.now(timezone.utc) - timedelta(hours=1)
    session.run(
        """
        MERGE (u:User {userId: $userId})
        MERGE (e1:Event {nodeId: 'test-retune-event-1'})
        SET e1.embedding = $vector, e1.occurredAt = $recent, e1.title = '홀드아웃 대상'
        MERGE (u)-[r1:CONSUMED]->(e1)
        SET r1.eventClickCount = 1, r1.lastViewedAt = $recent, r1.eventFavorited = false

        MERGE (e2:Event {nodeId: 'test-retune-event-2'})
        SET e2.embedding = $vector, e2.occurredAt = $recent, e2.title = '학습용 이력'
        MERGE (u)-[r2:CONSUMED]->(e2)
        SET r2.eventClickCount = 1, r2.lastViewedAt = $recent, r2.eventFavorited = false
        """,
        userId=EVAL_USER_ID,
        vector=_unit_vector(0),
        recent=recent,
    )


# evaluate_user_across_weight_grid이 평가용으로 지운 CONSUMED 관계를 무조건 롤백하는지 확인
def test_evaluate_user_across_weight_grid_does_not_persist_deletion():
    with _driver.session() as session:
        _reset_fixture(session)
        _seed_fixture(session)

    recommended_by_weight = service.evaluate_user_across_weight_grid(EVAL_USER_ID, ["test-retune-event-1"])
    assert set(recommended_by_weight.keys()) == set(service.WEIGHT_GRID)

    with _driver.session() as session:
        result = session.run(
            """
            MATCH (:User {userId: $userId})-[:CONSUMED]->(:Event {nodeId: 'test-retune-event-1'})
            RETURN count(*) AS c
            """,
            userId=EVAL_USER_ID,
        ).single()
    assert result["c"] == 1


# select_best_weights가 그리드 중 하나를 골라서 지표와 함께 반환하는지 확인
def test_select_best_weights_returns_a_grid_combination_with_valid_metrics():
    with _driver.session() as session:
        _reset_fixture(session)
        _seed_fixture(session)

    cbf_weight, cf_weight, ndcg, hit_rate, recall = service.select_best_weights()

    assert (cbf_weight, cf_weight) in service.WEIGHT_GRID
    assert 0.0 <= ndcg <= 1.0
    assert 0.0 <= hit_rate <= 1.0
    assert 0.0 <= recall <= 1.0
