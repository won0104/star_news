# Spring Boot가 추천 계산을 요청하는 내부 API.
from fastapi import APIRouter, Depends

from app.database import get_neo4j_session
from app.dependencies import verify_internal_service
from app.recommendations import service
from app.recommendations.schemas import RecommendationCalculateRequest

router = APIRouter(dependencies=[Depends(verify_internal_service)])


@router.post("/recommendations/calculate")
async def calculate_recommendations(request: RecommendationCalculateRequest, session=Depends(get_neo4j_session)) -> dict:
    result = service.calculate_recommendations(request, session)
    return {"data": result}
