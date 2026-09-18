# 추천 계산 비즈니스 로직.
import math
from datetime import datetime, timedelta, timezone

from neo4j import Session

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

        # 3) 실제 추천 계산 
        scored = calculate_interest_based_recommendations(user.user_id, session, is_cold_start=is_cold_start)

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

# CF/CBF 결합 가중치 기본값. 나중에 -84에서 튜닝.
DEFAULT_CBF_WEIGHT = 0.5
DEFAULT_CF_WEIGHT = 0.5

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

    # 점수 높은 순 정렬 후 상위 N개만
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
    scored.sort(key=lambda s: s.score, reverse=True)
    # 상위 FINAL_RECOMMENDATION_LIMIT개만 반환
    return scored[: repository.FINAL_RECOMMENDATION_LIMIT]
