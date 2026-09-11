# 추천 도메인 공용 스키마.
from pydantic import BaseModel

# 협업 필터링(CF) 결과 하나 - 관심 기반/관심 확장 추천이 공통으로 재사용하는 내부 자료구조
class CFCandidate(BaseModel):
    event_id: str
    cf_score: float

# 콘텐츠 기반 필터링(CBF) 결과 하나 - 관심 기반 추천이 재사용하는 내부 자료구조
class CBFCandidate(BaseModel):
    event_id: str
    content_score: float
