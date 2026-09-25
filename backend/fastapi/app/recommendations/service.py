# 추천 계산 비즈니스 로직.
import math
from datetime import datetime, timedelta, timezone

from neo4j import Session

from app.database import _driver
from app.recommendations import repository
from app.recommendations.schemas import (
    CBFCandidate,
    CFCandidate,
    RecommendationCalculateRequest,
    RecommendationCalculateResponse,
    RecommendationItem,
    ScoredEvent,
    UserRecommendationResult,
)

# 최근성 가중치 반감기(일). 이 날짜만큼 지나면 가중치가 절반으로 줄어듦.
RECENCY_HALF_LIFE_DAYS = 14

# 즐겨찾기한 Event는 가중치를 이만큼 배로 늘림.
FAVORITE_WEIGHT_MULTIPLIER = 2.0

# 인기도 점수의 최근성 감쇠 반감기(일).
POPULARITY_HALF_LIFE_DAYS = 3


# 관심 기반 추천 최종 계산 - Chunk로 묶인 유저들을 순회하며 각자 추천 결과를 조립한다
def calculate_recommendations(
    request: RecommendationCalculateRequest, session: Session
) -> RecommendationCalculateResponse:
    results: list[UserRecommendationResult] = []

    for user in request.users:
        # 1) Neo4j User Graph에 없는 유저는 이 유저만 건너뛰고 나머지는 정상 처리 (부분 성공)
        if not repository.user_exists(session, user.user_id):
            continue

        # 2) CONSUMED 이력 여부로 이번 결과가 CF+CBF 정상 계산인지 콜드스타트인지 판정
        is_cold_start = not repository.has_consumption_history(session, user.user_id)
        recommendation_type = "COLD_START" if is_cold_start else "NORMAL"

        # 3) 실제 추천 계산 - 요청에 재튜닝된 가중치가 실려있으면 그걸 쓰고, 없으면 기본값 사용
        scored = calculate_interest_based_recommendations(
            user.user_id,
            session,
            cbf_weight=request.cbf_weight if request.cbf_weight is not None else DEFAULT_CBF_WEIGHT,
            cf_weight=request.cf_weight if request.cf_weight is not None else DEFAULT_CF_WEIGHT,
            is_cold_start=is_cold_start,
        )

        # 후보가 하나도 없으면 (신규 Topic이라 인기 Event도 없는 등) 빈 목록으로 응답
        if not scored:
            results.append(UserRecommendationResult(user_id=user.user_id, items=[]))
            continue

        # 4) 응답에 필요한 화면 표시 정보(제목/대표 Topic)를 최종 추천 Event들에 대해서만 한 번에 조회
        display_info = repository.fetch_event_display_info(session, [s.event_id for s in scored])

        # 5) 점수 순서(scored가 이미 내림차순)를 그대로 rank로 매겨서 응답 아이템 조립
        items = [
            RecommendationItem(
                event_id=s.event_id,
                label=display_info.get(s.event_id, {}).get("label") or "",
                topic_code=display_info.get(s.event_id, {}).get("topicCode") or "",
                score=s.score,
                rank=rank,
                recommendation_type=recommendation_type,
            )
            for rank, s in enumerate(scored, start=1)
        ]
        results.append(UserRecommendationResult(user_id=user.user_id, items=items))

    return RecommendationCalculateResponse(cycle=request.cycle, results=results)

# CF/CBF 결합 가중치 기본값
# 초기 서비스라 유저 수가 적어 CF(유사 유저 기반)가 구조적으로 불리하므로 CBF 쪽으로 기울여 시작한다
DEFAULT_CBF_WEIGHT = 0.7
DEFAULT_CF_WEIGHT = 0.3

# 1. 협업 필터링(CF) 공용 모듈
def calculate_cf_scores(
    user_id: int,
    session: Session,
    interested_topic_codes: list[str] | None = None,
    recency_threshold: datetime | None = None,
) -> list[CFCandidate]:
    candidates = repository.find_cf_candidate_events(session, user_id, interested_topic_codes, recency_threshold)
    return [CFCandidate(event_id=c["eventId"], cf_score=c["cfScore"]) for c in candidates]

# 2. 콘텐츠 기반 필터링(CBF) 공용 모듈
# CONSUMED 이력 하나의 가중치 계산 - 많이 클릭할수록(로그 스케일), 최근에 볼수록(지수 감쇠) 가중치 증가
def _calculate_consumption_weight(
    event_click_count: int, last_viewed_at: datetime, now: datetime, is_favorited: bool
) -> float:
    days_since = max((now - last_viewed_at).total_seconds() / 86400, 0)
    # 반감기(RECENCY_HALF_LIFE_DAYS)를 감쇠 속도(λ)로 변환
    decay_rate = math.log(2) / RECENCY_HALF_LIFE_DAYS
    favorite_multiplier = FAVORITE_WEIGHT_MULTIPLIER if is_favorited else 1.0
    # weight = log(1 + eventClickCount) × exp(-λ × 경과일수) × favorite_multiplier
    return math.log1p(event_click_count) * math.exp(-decay_rate * days_since) * favorite_multiplier


# CONSUMED Event 임베딩들을 가중평균해서 유저 프로필 벡터 생성
def _build_user_profile_vector(consumed_events: list[dict]) -> list[float] | None:

    # CONSUMED 이력 없음 (Cold Start는 호출하는 쪽에서 처리)
    if not consumed_events:
        return None

    now = datetime.now(timezone.utc)
    weighted_sum: list[float] | None = None  # Σ(event_embedding × weight)
    total_weight = 0.0  # Σ(weight)

    for event in consumed_events:
        weight = _calculate_consumption_weight(
            event["eventClickCount"], event["lastViewedAt"], now, event["isFavorited"]
        )
        embedding = event["embedding"]
        if weighted_sum is None:
            weighted_sum = [0.0] * len(embedding)
        # 임베딩 차원별로 weight를 곱해서 누적
        for i, value in enumerate(embedding):
            weighted_sum[i] += value * weight
        total_weight += weight

    if total_weight == 0:
        return None

    # profile_vector = Σ(event_embedding × weight) / Σ(weight)
    return [value / total_weight for value in weighted_sum]


# CBF 벡터 검색 rawLimit 재시도 설정 - 필터 통과분이 부족할 때만 두 배씩 늘려서 재조회
_CBF_RAW_LIMIT_INITIAL = repository.CONTENT_SIMILAR_EVENT_LIMIT * 3
_CBF_RAW_LIMIT_MAX = 500


# 콘텐츠 기반 필터링(CBF) 공용 모듈. 유저 프로필 벡터로 유사 Event 검색.
# interested_topic_codes/recency_threshold를 넘기면 그 조건까지 벡터 검색 결과에 바로 적용됨 (없으면 필터 없이 전체 대상)
def calculate_cbf_scores(
    user_id: int,
    session: Session,
    interested_topic_codes: list[str] | None = None,
    recency_threshold: datetime | None = None,
) -> list[CBFCandidate]:
    # 1) 뭘 봤는지 조회
    consumed_events = repository.find_consumed_events_with_embeddings(session, user_id)

    # 2) 취향 벡터 계산
    profile_vector = _build_user_profile_vector(consumed_events)
    if profile_vector is None:
        return []

    # 3) 그 벡터랑 비슷한 Event 검색
    # 필터 통과분이 목표치(CONTENT_SIMILAR_EVENT_LIMIT)보다 적으면 rawLimit을 2배씩 늘려서 재시도한다
    raw_limit = _CBF_RAW_LIMIT_INITIAL
    while True:
        similar_events = repository.find_similar_events_by_vector(
            session, profile_vector, user_id, interested_topic_codes, recency_threshold, raw_limit
        )
        enough = len(similar_events) >= repository.CONTENT_SIMILAR_EVENT_LIMIT
        exhausted = raw_limit >= _CBF_RAW_LIMIT_MAX
        if enough or exhausted:
            break
        raw_limit = min(raw_limit * 2, _CBF_RAW_LIMIT_MAX)

    return [
        CBFCandidate(event_id=e["eventId"], content_score=e["contentScore"]) for e in similar_events
    ]


# 3. Cold Start (CONSUMED 이력 없는 유저) 폴백
# 인기도 점수 계산 - 많이 볼수록(로그 스케일), 최근 사건일수록(지수 감쇠) 점수 증가. CBF 가중치 계산과 같은 형태.
def _calculate_popularity_score(unique_consumers: int, occurred_at: datetime, now: datetime) -> float:
    days_since = max((now - occurred_at).total_seconds() / 86400, 0)
    decay_rate = math.log(2) / POPULARITY_HALF_LIFE_DAYS
    # score = log(1 + 소비한_유저수) × exp(-λ × 경과일수)
    return math.log1p(unique_consumers) * math.exp(-decay_rate * days_since)


# Story 기반 중복 제거 - 같은 Story에 속한 후보는 점수 제일 높은 것 하나만 남긴다
# Story가 없는 Event는 자기 자신만 속한 그룹으로 취급해 항상 그대로 남는다
def _dedupe_by_story(session: Session, scored: list[ScoredEvent], min_required: int) -> list[ScoredEvent]:
    if not scored:
        return scored
    story_ids = repository.fetch_event_story_ids(session, [s.event_id for s in scored])
    best_by_group: dict[str, ScoredEvent] = {}
    for s in scored:
        group_key = story_ids.get(s.event_id) or s.event_id
        current_best = best_by_group.get(group_key)
        if current_best is None or s.score > current_best.score:
            best_by_group[group_key] = s
    deduped = list(best_by_group.values())
    # 중복 제거했더니 min_required도 못 채우면(Story 데이터가 과하게 뭉쳐있는 경우), 원본을 그대로 반환한다
    return deduped if len(deduped) >= min_required else scored


# 관심 Topic 안에서(또는 없으면 전체에서) 인기도 순으로 Event를 뽑는 Cold Start 폴백
def get_cold_start_fallback(user_id: int, session: Session) -> list[ScoredEvent]:
    # 관심 Topic 조회
    topic_codes = repository.find_user_interested_topics(session, user_id)
    # 후보 조회 (아직 점수/정렬 없음)
    candidates = repository.find_events_with_consumer_counts(session, topic_codes)

    # 인기도 점수 계산
    now = datetime.now(timezone.utc)
    scored = [
        ScoredEvent(
            event_id=c["eventId"],
            score=_calculate_popularity_score(c["uniqueConsumers"], c["occurredAt"], now),
        )
        for c in candidates
    ]

    # 같은 Story의 중복 후보를 정리한 뒤, 점수 높은 순 정렬 후 상위 N개만
    scored = _dedupe_by_story(session, scored, repository.FALLBACK_EVENT_LIMIT)
    scored.sort(key=lambda s: s.score, reverse=True)
    return scored[: repository.FALLBACK_EVENT_LIMIT]


# 4. 관심 기반 추천 최종 계산 (CF + CBF 가중합)
# final_score = cbf_weight × cbf_score + cf_weight × cf_score
def calculate_final_score(cbf_score: float, cf_score: float, cbf_weight: float, cf_weight: float) -> float:
    return cbf_weight * cbf_score + cf_weight * cf_score


# 관심 기반 추천 메인 함수
# Cold Start면 인기도 폴백, 아니면 CF+CBF 가중합 계산 (공통 후보 조건은 CF/CBF 쿼리 안에서 각자 바로 적용됨)
def calculate_interest_based_recommendations(
    user_id: int,
    session: Session,
    cbf_weight: float = DEFAULT_CBF_WEIGHT,
    cf_weight: float = DEFAULT_CF_WEIGHT,
    is_cold_start: bool | None = None,
) -> list[ScoredEvent]:

    # 콜드 스타트 처리
    if is_cold_start is None:
        is_cold_start = not repository.has_consumption_history(session, user_id)
    if is_cold_start:
        return get_cold_start_fallback(user_id, session)

    # 관심 Topic/최근성 기준을 한 번만 계산해서 CF/CBF 양쪽에 그대로 넘김 (중복 조회 방지)
    interested_topic_codes = repository.find_user_interested_topics(session, user_id)
    recency_threshold = datetime.now(timezone.utc) - timedelta(days=repository.RECENCY_WINDOW_DAYS)

    cf_scores = {
        c.event_id: c.cf_score
        for c in calculate_cf_scores(user_id, session, interested_topic_codes, recency_threshold)
    }
    cbf_scores = {
        c.event_id: c.content_score
        for c in calculate_cbf_scores(user_id, session, interested_topic_codes, recency_threshold)
    }

    candidate_ids = set(cf_scores) | set(cbf_scores)

    scored = [
        ScoredEvent(
            event_id=event_id,
            score=calculate_final_score(
                cbf_scores.get(event_id, 0.0), cf_scores.get(event_id, 0.0), cbf_weight, cf_weight
            ),
        )
        for event_id in candidate_ids
    ]
    # 같은 Story의 중복 후보를 정리한 뒤, 점수 높은 순 정렬 후 상위 FINAL_RECOMMENDATION_LIMIT개만 반환
    scored = _dedupe_by_story(session, scored, repository.FINAL_RECOMMENDATION_LIMIT)
    scored.sort(key=lambda s: s.score, reverse=True)
    return scored[: repository.FINAL_RECOMMENDATION_LIMIT]


# 5. 가중치 재튜닝 (적응형 holdout 평가)
# CF/CBF 가중치 그리드서치용 오프라인 평가
# 유저별 CONSUMED 이력 중 최근 일부를 "정답"으로 숨기고, 나머지 이력만으로 추천을 계산해서 정답을 맞히는지로 채점

# holdout 비율 - "정답 후보(최근성 자격 있는 것)" 중 최근 20%를 정답으로 뗀다
HOLD_OUT_RATIO = 0.2
# 추천 Top-K - 지표(NDCG/HitRate/Recall) 계산 시 몇 등까지 볼지
EVAL_TOP_K = 10
# 그리드서치 대상 (cbf_weight, cf_weight) 조합 - cbf_weight + cf_weight = 1 고정, 0.1 단위로 11개
WEIGHT_GRID = [(round(1 - i * 0.1, 1), round(i * 0.1, 1)) for i in range(11)]


# 유저별 (event_id, 최근성 자격) 이력을 받아서, 평가 가능한 유저만 남기고 (정답 목록, 학습용 목록)으로 나눈다
def build_holdout_splits(all_histories: dict[int, list[dict]]) -> dict[int, tuple[list[str], list[str]]]:
    splits = {}
    for user_id, history in all_histories.items():
        # 정답은 최근성 자격 있는 것 중에서만 고르고(안 그러면 절대 못 맞힐 정답을 놓고 채점하게 됨),
        # 학습용은 원래 이력 전체를 그대로 둔다(프로필 벡터 계산은 실제 서비스도 기간 제한이 없어서)
        full_ids = [item["eventId"] for item in history]
        eligible_ids = [item["eventId"] for item in history if item["isRecencyEligible"]]
        if not eligible_ids:
            continue
        # 자격 있는 이력 개수의 20%를 정답 개수로 - 소수점은 반올림하되 최소 1개는 보장
        hold_out_count = max(1, round(len(eligible_ids) * HOLD_OUT_RATIO))
        # eligible_ids는 최근순 정렬이라 앞쪽 hold_out_count개 = 가장 최근 정답
        held_out = eligible_ids[:hold_out_count]
        held_out_set = set(held_out)
        # 학습용은 정답으로 뽑히지 않은 나머지 전체(오래된 것 포함)
        visible = [eid for eid in full_ids if eid not in held_out_set]
        if not visible:
            continue

        splits[user_id] = (held_out, visible)
    return splits


# 추천 Top-K와 정답(held_out) 집합을 비교해서 채점하는 지표 3개
# 1) NDCG@10 (순위까지 반영) - 앞쪽에서 맞힐수록 점수가 높음, 자기 정답 개수 기준 이상적인 순위(IDCG)로 나눠 정규화
def calculate_ndcg_at_k(recommended_ids: list[str], held_out: set[str], k: int = EVAL_TOP_K) -> float:
    dcg = sum(1 / math.log2(i + 2) for i, eid in enumerate(recommended_ids[:k]) if eid in held_out)
    idcg = sum(1 / math.log2(i + 2) for i in range(min(len(held_out), k)))
    return dcg / idcg if idcg else 0.0


# 2) Hit Rate@10 - Top-K 안에 정답이 하나라도 있으면 1, 없으면 0 (이진값)
def calculate_hit_rate_at_k(recommended_ids: list[str], held_out: set[str], k: int = EVAL_TOP_K) -> float:
    return 1.0 if set(recommended_ids[:k]) & held_out else 0.0


# 3) Recall@10 - Top-K 중 정답을 몇 % 맞혔는지 (숨긴 정답 개수 대비)
def calculate_recall_at_k(recommended_ids: list[str], held_out: set[str], k: int = EVAL_TOP_K) -> float:
    return len(set(recommended_ids[:k]) & held_out) / len(held_out) if held_out else 0.0


# 정답(held_out) 이벤트의 CONSUMED 관계를 트랜잭션 안에서만 지우고,추천을 계산한 뒤 롤백
def evaluate_user_across_weight_grid(user_id: int, held_out_ids: list[str]) -> dict[tuple[float, float], list[str]]:
    with _driver.session() as session:
        tx = session.begin_transaction()
        try:
            tx.run(
                """
                MATCH (:User {userId: $userId})-[r:CONSUMED]->(e:Event)
                WHERE e.nodeId IN $heldOutIds
                DELETE r
                """,
                userId=user_id,
                heldOutIds=held_out_ids,
            )
            return {
                (cbf_weight, cf_weight): [
                    s.event_id
                    for s in calculate_interest_based_recommendations(
                        user_id, tx, cbf_weight=cbf_weight, cf_weight=cf_weight
                    )
                ]
                for cbf_weight, cf_weight in WEIGHT_GRID
            }
        finally:
            tx.rollback()


# 재튜닝 한 번에 cbf_weight가 직전 값 대비 최대 이만큼만 움직이게 제한(그리드 간격 1칸) - 노이즈로 값이 널뛰는 것 방지
MAX_WEIGHT_STEP = 0.1


# 재튜닝 메인 함수 - 그리드서치 전체를 돌려서 NDCG@10이 가장 높은 (cbf_weight, cf_weight) 조합을 고른다
def select_best_weights(current_cbf_weight: float | None = None) -> tuple[float, float, float, float, float]:
    # 홀드아웃 정답 자격 판단에도 실제 추천 후보 조건과 같은 최근성 기준을 쓴다
    recency_threshold = datetime.now(timezone.utc) - timedelta(days=repository.RECENCY_WINDOW_DAYS)
    with _driver.session() as session:
        all_histories = repository.find_users_eligible_for_evaluation(session, recency_threshold)
    splits = build_holdout_splits(all_histories)

    # 평가 가능한 유저가 없으면 그리드서치가 무의미하니 현재 기본값을 그대로 반환
    if not splits:
        return DEFAULT_CBF_WEIGHT, DEFAULT_CF_WEIGHT, 0.0, 0.0, 0.0

    # 가중치 조합별로 유저들의 (ndcg, hit_rate, recall)을 누적
    metrics_by_weight: dict[tuple[float, float], list[tuple[float, float, float]]] = {
        combo: [] for combo in WEIGHT_GRID
    }
    for user_id, (held_out, _visible) in splits.items():
        held_out_set = set(held_out)
        try:
            recommended_by_weight = evaluate_user_across_weight_grid(user_id, held_out)
        except Exception:
            continue  # 이 유저 처리 중 에러나도 나머지는 계속 진행
        for combo, recommended in recommended_by_weight.items():
            metrics_by_weight[combo].append(
                (
                    calculate_ndcg_at_k(recommended, held_out_set),
                    calculate_hit_rate_at_k(recommended, held_out_set),
                    calculate_recall_at_k(recommended, held_out_set),
                )
            )

    if all(not scores for scores in metrics_by_weight.values()):
        return DEFAULT_CBF_WEIGHT, DEFAULT_CF_WEIGHT, 0.0, 0.0, 0.0

    # 직전 값이 있으면 그 값 기준 ±MAX_WEIGHT_STEP 안의 조합에서만 고른다(급변 방지)
    candidate_grid = WEIGHT_GRID
    if current_cbf_weight is not None:
        candidate_grid = [
            combo for combo in WEIGHT_GRID if abs(combo[0] - current_cbf_weight) <= MAX_WEIGHT_STEP + 1e-9
        ] or WEIGHT_GRID  # 직전 값이 그리드에서 너무 벗어나 있는 등 비정상 상황이면 안전하게 전체로 폴백

    averaged: dict[tuple[float, float], tuple[float, float, float]] = {}
    for combo in candidate_grid:
        scores = metrics_by_weight[combo]
        avg_ndcg = sum(s[0] for s in scores) / len(scores) if scores else 0.0
        avg_hit = sum(s[1] for s in scores) / len(scores) if scores else 0.0
        avg_recall = sum(s[2] for s in scores) / len(scores) if scores else 0.0
        averaged[combo] = (avg_ndcg, avg_hit, avg_recall)

    # NDCG 최고점을 찍은 조합이 여럿(동률)이면
    # 그중 직전 값(없으면 기본값)에 가장 가까운 것을 고른다 - 그리드 순서에 따른 임의 편향을 없애기 위함
    best_ndcg = max(avg[0] for avg in averaged.values())
    reference = current_cbf_weight if current_cbf_weight is not None else DEFAULT_CBF_WEIGHT
    cbf_weight, cf_weight = min(
        (combo for combo, avg in averaged.items() if avg[0] == best_ndcg),
        key=lambda combo: abs(combo[0] - reference),
    )
    ndcg, hit_rate, recall = averaged[(cbf_weight, cf_weight)]
    return cbf_weight, cf_weight, ndcg, hit_rate, recall
