"""Long-lived HTTP worker for article inference."""

from __future__ import annotations

import logging
from collections.abc import Callable
from contextlib import asynccontextmanager
from threading import Lock
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from starlight_ai.pipeline import ArticleAnalyzer, process_article

logger = logging.getLogger(__name__)


class ArticleAnalyzeRequest(BaseModel):
    article_id: str
    mysql_article_id: int | None = None
    title: str
    content: str
    published_at: str


class WorkerState:
    """프로세스 하나가 analyzer 하나를 소유하고 모든 요청에서 재사용한다."""

    def __init__(self, analyzer_factory: Callable[[], ArticleAnalyzer]) -> None:
        self._analyzer_factory = analyzer_factory
        self._analyzer: ArticleAnalyzer | None = None
        self._lock = Lock()

    @property
    def ready(self) -> bool:
        return self._analyzer is not None and self._analyzer.is_loaded

    def load(self) -> None:
        # 서버 시작 단계에서 모델을 모두 RAM에 올린다.
        # 첫 요청이 모델 로딩까지 떠안지 않게 하고, 준비 전에는 readiness가 성공하지 않는다.
        analyzer = self._analyzer_factory()
        analyzer.load()
        self._analyzer = analyzer

    def close(self) -> None:
        self._analyzer = None

    def analyze(self, article: dict[str, Any]) -> dict[str, Any]:
        analyzer = self._analyzer
        if analyzer is None or not analyzer.is_loaded:
            raise RuntimeError("AI worker is not ready")
        # 모델 객체는 여러 요청이 동시에 접근하는 상황을 전제로 하지 않는다.
        # 한 번에 기사 하나만 추론해 메모리 급증과 모델 내부 상태 충돌을 막는다.
        with self._lock:
            return process_article(article, analyzer=analyzer)


def create_app(
    analyzer_factory: Callable[[], ArticleAnalyzer] = ArticleAnalyzer,
) -> FastAPI:
    worker = WorkerState(analyzer_factory)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        # lifespan의 yield 전에 로딩하므로 모델 준비가 끝나야 서버 startup이 완료된다.
        logger.info("Loading AI models")
        worker.load()
        logger.info("AI models loaded")
        try:
            yield
        finally:
            worker.close()

    app = FastAPI(title="starlight-ai-worker", lifespan=lifespan)
    app.state.worker = worker

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "UP"}

    @app.get("/ready")
    def ready() -> dict[str, str]:
        if not worker.ready:
            raise HTTPException(status_code=503, detail="AI models are not loaded")
        return {"status": "READY"}

    @app.post("/internal/v1/articles/analyze")
    def analyze(request: ArticleAnalyzeRequest) -> dict[str, Any]:
        try:
            return worker.analyze(request.model_dump(exclude_none=True))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            if not worker.ready:
                raise HTTPException(status_code=503, detail=str(exc)) from exc
            logger.exception("AI inference failed")
            raise HTTPException(status_code=500, detail="AI inference failed") from exc
        except Exception as exc:
            logger.exception("AI inference failed")
            raise HTTPException(status_code=500, detail="AI inference failed") from exc

    return app


app = create_app()
