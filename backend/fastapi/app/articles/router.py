# Spring Boot가 기사 분석을 요청하는 내부 API. 인증 통과 후 service로 위임만 한다.
from fastapi import APIRouter, Depends

from app.articles import service
from app.dependencies import verify_internal_service

router = APIRouter(dependencies=[Depends(verify_internal_service)])


@router.post("/articles/analyze")
async def analyze_article(request: dict):
    return service.analyze_article(request)
