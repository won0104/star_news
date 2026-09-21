from fastapi import APIRouter, Depends

from app.database import get_neo4j_session
from app.dependencies import verify_internal_service
from app.recommendations import service
from app.recommendations.schemas import RecommendationCalculateRequest, RecommendationRetuneResult

router = APIRouter(dependencies=[Depends(verify_internal_service)])

# 안의 Neo4j 호출이 동기라 async def 가 아닌 def 로 둔다. async def 면 처리 중 이벤트 루프가 막혀
# 다른 요청까지 멈춘다. def 는 FastAPI 가 스레드풀에서 실행한다.

# Spring Boot가 추천 계산을 요청하는 내부 API
@router.post("/recommendations/calculate")
def calculate_recommendations(request: RecommendationCalculateRequest, session=Depends(get_neo4j_session)) -> dict:
    result = service.calculate_recommendations(request, session)
    return {"data": result}


# 호출될 때마다 그리드서치 전체를 새로 돌려서 최적 가중치를 반환하는 내부 API
@router.post("/recommendations/retune")
def retune_recommendations() -> dict:
    cbf_weight, cf_weight, ndcg, hit_rate, recall = service.select_best_weights()
    result = RecommendationRetuneResult(
        cbf_weight=cbf_weight,
        cf_weight=cf_weight,
        ndcg_at_10=ndcg,
        hit_rate_at_10=hit_rate,
        recall_at_10=recall,
    )
    return {"data": result}
