# 추천 도메인 공용 스키마.
from pydantic import BaseModel


class CFCandidate(BaseModel):
    # 협업 필터링(CF) 결과 하나 - 관심 기반/관심 확장 추천이 공통으로 재사용하는 내부 자료구조
    event_id: str
    cf_score: float
