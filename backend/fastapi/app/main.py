# FastAPI 앱 진입점.
from fastapi import FastAPI

from app.articles.router import router as articles_router
from app.config import settings
from app.exceptions import register_exception_handlers
from app.health import router as health_router
from app.recommendations.router import router as recommendations_router
from app.user_graph.router import router as user_graph_router

app = FastAPI(title=settings.app_name)

# 전역 예외 핸들러 등록
register_exception_handlers(app)

# 도메인별 라우터 등록
app.include_router(health_router, tags=["health"])
app.include_router(articles_router, prefix="/internal/v1", tags=["articles"])
app.include_router(recommendations_router, prefix="/internal/v1", tags=["recommendations"])
app.include_router(user_graph_router, prefix="/internal/v1", tags=["user-graph"])
