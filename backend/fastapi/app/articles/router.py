from fastapi import APIRouter, Depends

from app.articles import service
from app.articles.schemas import ArticleAnalyzeRequest
from app.database import get_neo4j_session
from app.dependencies import verify_internal_service

router = APIRouter(dependencies=[Depends(verify_internal_service)])

# Spring Boot가 기사 분석을 요청하는 내부 API.
# async 가 아닌 def 로 둔다. 안에서 AI 워커 HTTP 호출과 Neo4j 호출이 모두 동기라, async def 면
# 분석 한 건(수십 초) 동안 이벤트 루프가 막혀 다른 요청(추천 계산 등)까지 멈춘다.
# def 로 두면 FastAPI 가 스레드풀에서 실행한다.
@router.post("/articles/analyze")
def analyze_article(request: ArticleAnalyzeRequest, session=Depends(get_neo4j_session)) -> dict:
    result = service.analyze_article(request, session)
    return {"data": result}
