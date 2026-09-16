"""AI worker tests that do not require model weights."""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT))

from starlight_ai.server import create_app


ARTICLE = {
    "article_id": "article-1",
    "mysql_article_id": 1,
    "title": "테스트 기사",
    "content": "테스트 기사 본문입니다.",
    "published_at": "2026-09-16T12:00:00+09:00",
}


class FakeAnalyzer:
    device = "cpu"

    def __init__(self) -> None:
        self.load_count = 0
        self.process_count = 0

    @property
    def is_loaded(self) -> bool:
        return self.load_count == 1

    def load(self) -> None:
        self.load_count += 1

    def process(self, article: dict) -> dict:
        self.process_count += 1
        return {
            "schema_version": "starlight-article-analyze-v1",
            "article_id": article["article_id"],
            "classification": {},
            "nodes": [],
            "edges": [],
        }


def test_worker_loads_once_and_reuses_analyzer() -> None:
    analyzer = FakeAnalyzer()
    app = create_app(lambda: analyzer)

    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "UP"}
        assert client.get("/ready").json() == {"status": "READY"}

        first = client.post("/internal/v1/articles/analyze", json=ARTICLE)
        second = client.post("/internal/v1/articles/analyze", json=ARTICLE)

    assert first.status_code == 200
    assert second.status_code == 200
    assert analyzer.load_count == 1
    assert analyzer.process_count == 2
    assert first.json()["meta"]["device"] == "cpu"


def test_worker_rejects_invalid_request_before_inference() -> None:
    analyzer = FakeAnalyzer()
    app = create_app(lambda: analyzer)

    invalid = {**ARTICLE, "content": None}
    with TestClient(app) as client:
        response = client.post("/internal/v1/articles/analyze", json=invalid)

    assert response.status_code == 422
    assert analyzer.process_count == 0
