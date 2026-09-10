# 추천 계산 비즈니스 로직.
from datetime import datetime, timedelta, timezone

from neo4j import Session

from app.recommendations import repository
from app.recommendations.schemas import CFCandidate


# 관심 기반/관심 확장 추천 최종 계산
def calculate_recommendations(request: dict):
    raise NotImplementedError


# 협업 필터링(CF) 공용 모듈
def calculate_cf_scores(user_id: int, session: Session) -> list[CFCandidate]:
    candidates = repository.find_cf_candidate_events(session, user_id)
    return [CFCandidate(event_id=c["eventId"], cf_score=c["cfScore"]) for c in candidates]


# 추천 후보 공통 필터링 공용 모듈
def get_eligible_candidate_event_ids(user_id: int, session: Session) -> set[str]:
    recency_threshold = datetime.now(timezone.utc) - timedelta(days=repository.RECENCY_WINDOW_DAYS)
    return set(repository.find_candidate_events(session, user_id, recency_threshold))
