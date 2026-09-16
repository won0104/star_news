# 추천 계산 비즈니스 로직.
import math
from datetime import datetime, timedelta, timezone

from neo4j import Session

from app.recommendations import repository
from app.recommendations.schemas import CBFCandidate, CFCandidate, ScoredEvent

# 최근성 가중치 반감기(일). 이 날짜만큼 지나면 가중치가 절반으로 줄어듦.
RECENCY_HALF_LIFE_DAYS = 14

# 즐겨찾기한 Event는 가중치를 이만큼 배로 늘림.
FAVORITE_WEIGHT_MULTIPLIER = 2.0

# 인기도 점수의 최근성 감쇠 반감기(일).
POPULARITY_HALF_LIFE_DAYS = 3


# 관심 기반/관심 확장 추천 최종 계산
def calculate_recommendations(request: dict):
    raise NotImplementedError

# CF/CBF 결합 가중치 기본값. 나중에 -84에서 튜닝.
DEFAULT_CBF_WEIGHT = 0.5
DEFAULT_CF_WEIGHT = 0.5

# 1. 추천 후보 공통 필터링 공용 모듈
def get_eligible_candidate_event_ids(user_id: int, session: Session) -> set[str]:
    recency_threshold = datetime.now(timezone.utc) - timedelta(days=repository.RECENCY_WINDOW_DAYS)
    return set(repository.find_candidate_events(session, user_id, recency_threshold))

# 2. 협업 필터링(CF) 공용 모듈
def calculate_cf_scores(user_id: int, session: Session) -> list[CFCandidate]:
    candidates = repository.find_cf_candidate_events(session, user_id)
    return [CFCandidate(event_id=c["eventId"], cf_score=c["cfScore"]) for c in candidates]

# 3. 콘텐츠 기반 필터링(CBF) 공용 모듈
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


# 콘텐츠 기반 필터링(CBF) 공용 모듈. 유저 프로필 벡터로 유사 Event 검색.
def calculate_cbf_scores(user_id: int, session: Session) -> list[CBFCandidate]:
    # 1) 뭘 봤는지 조회
    consumed_events = repository.find_consumed_events_with_embeddings(session, user_id)

    # 2) 취향 벡터 계산
    profile_vector = _build_user_profile_vector(consumed_events)
    if profile_vector is None:
        return []

    # 3) 그 벡터랑 비슷한 Event 검색
    similar_events = repository.find_similar_events_by_vector(session, profile_vector, user_id)
    return [
        CBFCandidate(event_id=e["eventId"], content_score=e["contentScore"]) for e in similar_events
    ]


# 4. Cold Start (CONSUMED 이력 없는 유저) 폴백
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


# 5. 관심 기반 추천 최종 계산 (CF + CBF 가중합)
# final_score = cbf_weight × cbf_score + cf_weight × cf_score
def calculate_final_score(cbf_score: float, cf_score: float, cbf_weight: float, cf_weight: float) -> float:
    return cbf_weight * cbf_score + cf_weight * cf_score


# 관심 기반 추천 메인 함수
# Cold Start면 인기도 폴백, 아니면 후보 필터링 ∩ (CF+CBF 가중합) 계산
def calculate_interest_based_recommendations(
    user_id: int,
    session: Session,
    cbf_weight: float = DEFAULT_CBF_WEIGHT,
    cf_weight: float = DEFAULT_CF_WEIGHT,
) -> list[ScoredEvent]:

    # 콜드 스타트 처리
    if not repository.has_consumption_history(session, user_id):
        return get_cold_start_fallback(user_id, session)

    # 후보 필터링 ∩ (CF+CBF 가중합) 계산
    eligible_ids = get_eligible_candidate_event_ids(user_id, session)
    cf_scores = {c.event_id: c.cf_score for c in calculate_cf_scores(user_id, session)}
    cbf_scores = {c.event_id: c.content_score for c in calculate_cbf_scores(user_id, session)}

    # CF든 CBF든 하나라도 점수가 있는 Event 중, 후보 필터링을 통과한 것만 최종 후보로 남김
    candidate_ids = (set(cf_scores) | set(cbf_scores)) & eligible_ids

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
    # 상위 5개 반환
    return scored[: repository.FINAL_RECOMMENDATION_LIMIT]
