from fastapi import APIRouter, Depends

from app.articles import service
from app.articles.schemas import ArticleAnalyzeRequest
from app.dependencies import verify_internal_service

router = APIRouter(dependencies=[Depends(verify_internal_service)])

# Spring Boot가 기사 분석을 요청하는 내부 API.
@router.post("/articles/analyze")
async def analyze_article(request: ArticleAnalyzeRequest) -> dict:
    result = service.analyze_article(request)
    return {"data": result}
