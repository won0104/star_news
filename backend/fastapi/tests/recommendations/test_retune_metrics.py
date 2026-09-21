from app.recommendations.service import (
    build_holdout_splits,
    calculate_hit_rate_at_k,
    calculate_ndcg_at_k,
    calculate_recall_at_k,
)


# NDCG@10: 정답을 전부, 순서까지 이상적으로(앞쪽에) 맞히면 DCG=IDCG라 만점
def test_calculate_ndcg_at_k_perfect_order_scores_one():
    assert calculate_ndcg_at_k(["a", "b", "x"], {"a", "b"}) == 1.0


# 정답이 뒤로 밀릴수록 로그 감쇠로 점수가 깎여서 만점보다 낮아야 함
def test_calculate_ndcg_at_k_out_of_order_scores_less_than_one():
    score = calculate_ndcg_at_k(["x", "a", "b"], {"a", "b"})
    assert 0.0 < score < 1.0


# Top-K 안에 정답이 하나도 없으면 0
def test_calculate_ndcg_at_k_no_hits_scores_zero():
    assert calculate_ndcg_at_k(["x", "y"], {"a", "b"}) == 0.0


# Hit Rate@10: 정답이 몇 개 맞든 상관없이 하나라도 있으면 1, 없으면 0 (이진값)
def test_calculate_hit_rate_at_k_is_binary_regardless_of_hit_count():
    assert calculate_hit_rate_at_k(["a", "b", "x"], {"a", "b"}) == 1.0
    assert calculate_hit_rate_at_k(["x", "y"], {"a", "b"}) == 0.0


# Recall@10: 숨긴 정답 개수 대비 맞힌 비율
def test_calculate_recall_at_k_computes_ratio_against_held_out_count():
    assert calculate_recall_at_k(["a", "x", "y"], {"a", "b"}) == 0.5
    assert calculate_recall_at_k(["a", "b"], {"a", "b"}) == 1.0


# 이력이 MIN_HISTORY_FOR_EVAL(2) 미만이면 홀드아웃 자체가 불가능해서 평가 대상에서 빠져야 함
def test_build_holdout_splits_excludes_users_with_too_short_history():
    splits = build_holdout_splits({1: ["only-one"], 2: ["e1", "e2"]})
    assert 1 not in splits
    assert 2 in splits


# 이력(최근순 정렬 가정)의 앞쪽 20%(반올림, 최소 1개)를 정답으로 떼고 나머지는 학습용으로 남기는지 확인
def test_build_holdout_splits_takes_most_recent_20_percent_as_held_out():
    history = ["newest", "e2", "e3", "e4", "oldest"]  # round(5 * 0.2) == 1
    held_out, visible = build_holdout_splits({1: history})[1]
    assert held_out == ["newest"]
    assert visible == ["e2", "e3", "e4", "oldest"]


# 이력이 적어도(2개) 20%가 0에 가까워지는 극단값에서, 최소 1개는 보장되는지 확인
def test_build_holdout_splits_holds_out_at_least_one_even_for_minimum_history():
    held_out, visible = build_holdout_splits({1: ["newest", "oldest"]})[1]
    assert held_out == ["newest"]
    assert visible == ["oldest"]
