# 추천 도메인 공용 스키마.
from typing import Literal

from pydantic import BaseModel

from app.base_schema import CamelModel

# 협업 필터링(CF) 결과 하나 - 관심 기반/관심 확장 추천이 공통으로 재사용하는 내부 자료구조
class CFCandidate(BaseModel):
    event_id: str
    cf_score: float

# 콘텐츠 기반 필터링(CBF) 결과 하나 - 관심 기반 추천이 재사용하는 내부 자료구조
class CBFCandidate(BaseModel):
    event_id: str
    content_score: float

# 최종 추천 결과 하나 - 콘텐츠 점수/CF 점수를 가중합한 최종 점수
class ScoredEvent(BaseModel):
    event_id: str
    score: float


# POST /internal/v1/recommendations/calculate 요청/응답 스키마 (Spring Batch <-> FastAPI 계약)
# 유저 한 명의 추천 요청
class UserRecommendationRequest(CamelModel):
    user_id: int
    limit: int


# Chunk 단위 요청 전체 - 여러 유저를 한 번에 묶어서 보냄
class RecommendationCalculateRequest(CamelModel):
    cycle: Literal["AM", "PM"]
    users: list[UserRecommendationRequest]
    # 재튜닝된 가중치 - 없으면 서비스 쪽 기본값(DEFAULT_CBF_WEIGHT/DEFAULT_CF_WEIGHT)
    cbf_weight: float | None = None
    cf_weight: float | None = None


# 추천 결과 하나(Event 하나) - 화면 표시에 필요한 정보
class RecommendationItem(CamelModel):
    event_id: str
    label: str
    topic_code: str
    score: float
    rank: int
    recommendation_type: Literal["NORMAL", "COLD_START"]


# 유저 한 명에 대한 추천 결과 목록
class UserRecommendationResult(CamelModel):
    user_id: int
    items: list[RecommendationItem]


# Chunk 단위 응답 전체
class RecommendationCalculateResponse(CamelModel):
    cycle: Literal["AM", "PM"]
    results: list[UserRecommendationResult]


# POST /internal/v1/recommendations/retune 응답 스키마
class RecommendationRetuneResult(CamelModel):
    cbf_weight: float
    cf_weight: float
    ndcg_at_10: float
    hit_rate_at_10: float
    recall_at_10: float
