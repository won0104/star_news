from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.config import settings
from app.database import _driver
from app.main import app
from app.recommendations import service

client = TestClient(app)

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


# current_cbf_weight를 넘기면, 전체 그리드에서 최고점이 아니라 그 값 기준 ±MAX_WEIGHT_STEP 안에서만 골라야 함
def test_select_best_weights_clamps_to_current_weight_plus_minus_max_step():
    with _driver.session() as session:
        _reset_fixture(session)
        _seed_fixture(session)

    # 그리드 왼쪽 끝(0.0) 기준 - cbf_weight는 0.0 또는 0.1만 나올 수 있음
    cbf_weight, _cf_weight, _ndcg, _hit_rate, _recall = service.select_best_weights(current_cbf_weight=0.0)
    assert cbf_weight in {0.0, 0.1}

    # 그리드 오른쪽 끝(1.0) 기준 - cbf_weight는 0.9 또는 1.0만 나올 수 있음
    cbf_weight, _cf_weight, _ndcg, _hit_rate, _recall = service.select_best_weights(current_cbf_weight=1.0)
    assert cbf_weight in {0.9, 1.0}


# NDCG 최고점 후보를 조합별로 다르게 조작해서, 동률(0.9/0.1 vs 0.6/0.4)일 때 그리드 순서(0.9쪽이 먼저 나옴)가
# 아니라 기준값(기본값 0.7)에 더 가까운 쪽(0.6/0.4)을 고르는지 확인
def test_select_best_weights_breaks_ties_by_distance_to_reference(monkeypatch):
    monkeypatch.setattr(service.repository, "find_users_eligible_for_evaluation", lambda session, recency_threshold: {1: []})
    monkeypatch.setattr(service, "build_holdout_splits", lambda all_histories: {1: (["held-1"], ["visible-1"])})

    def fake_evaluate(user_id, held_out_ids):
        return {
            combo: (["held-1"] if combo in {(0.9, 0.1), (0.6, 0.4)} else ["other"])
            for combo in service.WEIGHT_GRID
        }

    monkeypatch.setattr(service, "evaluate_user_across_weight_grid", fake_evaluate)

    cbf_weight, cf_weight, ndcg, _hit_rate, _recall = service.select_best_weights()

    assert (cbf_weight, cf_weight) == (0.6, 0.4)
    assert ndcg == 1.0


# 모든 조합이 동률(전부 0)로 나오는 퇴화 상황 - 그리드 첫 항목(1.0/0.0)이 아니라 기본값(0.7/0.3)을 골라야 함
def test_select_best_weights_falls_back_to_default_when_every_combo_ties_at_zero(monkeypatch):
    monkeypatch.setattr(service.repository, "find_users_eligible_for_evaluation", lambda session, recency_threshold: {1: []})
    monkeypatch.setattr(service, "build_holdout_splits", lambda all_histories: {1: (["held-1"], ["visible-1"])})
    monkeypatch.setattr(
        service, "evaluate_user_across_weight_grid", lambda user_id, held_out_ids: {combo: ["other"] for combo in service.WEIGHT_GRID}
    )

    cbf_weight, cf_weight, ndcg, hit_rate, recall = service.select_best_weights()

    assert (cbf_weight, cf_weight) == (service.DEFAULT_CBF_WEIGHT, service.DEFAULT_CF_WEIGHT)
    assert (ndcg, hit_rate, recall) == (0.0, 0.0, 0.0)


# current_cbf_weight가 있으면, 평가 가능한 유저가 아예 없어도 기본값이 아니라 직전 값을 그대로 유지해야 함
# (안 그러면 데이터가 잠깐 없었다는 이유만으로 가중치가 기본값으로 확 튀어서 ±MAX_WEIGHT_STEP 제한이 무의미해짐)
def test_select_best_weights_keeps_current_weight_when_no_eligible_users(monkeypatch):
    monkeypatch.setattr(service.repository, "find_users_eligible_for_evaluation", lambda session, recency_threshold: {})

    cbf_weight, cf_weight, ndcg, hit_rate, recall = service.select_best_weights(current_cbf_weight=0.4)

    assert (cbf_weight, cf_weight) == (0.4, 0.6)
    assert (ndcg, hit_rate, recall) == (0.0, 0.0, 0.0)


# current_cbf_weight가 있으면, 유저 평가가 전부 예외로 실패해도 기본값이 아니라 직전 값을 유지해야 함
def test_select_best_weights_keeps_current_weight_when_every_evaluation_fails(monkeypatch):
    monkeypatch.setattr(service.repository, "find_users_eligible_for_evaluation", lambda session, recency_threshold: {1: []})
    monkeypatch.setattr(service, "build_holdout_splits", lambda all_histories: {1: (["held-1"], ["visible-1"])})

    def failing_evaluate(user_id, held_out_ids):
        raise RuntimeError("boom")

    monkeypatch.setattr(service, "evaluate_user_across_weight_grid", failing_evaluate)

    cbf_weight, cf_weight, ndcg, hit_rate, recall = service.select_best_weights(current_cbf_weight=0.4)

    assert (cbf_weight, cf_weight) == (0.4, 0.6)
    assert (ndcg, hit_rate, recall) == (0.0, 0.0, 0.0)


# /retune는 요청 본문이 완전히 새로 생긴 필드라, Spring 배포 순서와 무관하게 깨지면 안 됨:
# 구버전 Spring(본문 없음 또는 빈 {}) / 신버전 Spring(currentCbfWeight 포함) 셋 다 확인
def test_retune_endpoint_accepts_missing_or_empty_or_full_request_body():
    headers = {"x-internal-api-key": settings.internal_api_key}

    no_body = client.post("/internal/v1/recommendations/retune", headers=headers)
    empty_body = client.post("/internal/v1/recommendations/retune", headers=headers, json={})
    full_body = client.post(
        "/internal/v1/recommendations/retune", headers=headers,
        json={"currentCbfWeight": 0.7, "currentCfWeight": 0.3},
    )

    for response in (no_body, empty_body, full_body):
        assert response.status_code == 200
        assert "cbfWeight" in response.json()["data"]
