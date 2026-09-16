from fastapi import APIRouter, Depends

from app.articles import service
from app.articles.schemas import ArticleAnalyzeRequest
from app.database import get_neo4j_session
from app.dependencies import verify_internal_service

router = APIRouter(dependencies=[Depends(verify_internal_service)])

# Spring Boot가 기사 분석을 요청하는 내부 API.
@router.post("/articles/analyze")
async def analyze_article(request: ArticleAnalyzeRequest, session=Depends(get_neo4j_session)) -> dict:
    result = service.analyze_article(request, session)
    return {"data": result}
