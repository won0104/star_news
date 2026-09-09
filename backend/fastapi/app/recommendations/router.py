# Spring Boot가 추천 계산을 요청하는 내부 API.
from fastapi import APIRouter, Depends

from app.dependencies import verify_internal_service
from app.recommendations import service

router = APIRouter(dependencies=[Depends(verify_internal_service)])


@router.post("/recommendations/calculate")
async def calculate_recommendations(request: dict):
    return service.calculate_recommendations(request)
