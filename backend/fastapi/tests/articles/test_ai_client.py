"""FastAPI -> AI worker HTTP client behavior."""

from datetime import datetime

import httpx
import pytest

from app.articles import service
from app.articles.schemas import ArticleAnalyzeRequest
from app.exceptions import AppException


def _request() -> ArticleAnalyzeRequest:
    return ArticleAnalyzeRequest(
        article_id=101,
        title="테스트 기사",
        content="테스트 기사 본문입니다.",
        source_id=1,
        source_name="테스트뉴스",
        published_at=datetime.fromisoformat("2026-09-16T12:00:00+09:00"),
    )


def _valid_result() -> dict:
    return {
        "classification": {"topic": "경제", "small_cls": "취업_창업"},
        "nodes": [],
        "edges": [],
    }


def test_call_ai_sends_worker_contract(monkeypatch) -> None:
    captured = {}

    def fake_post(url, *, json, timeout):
        captured.update(url=url, json=json, timeout=timeout)
        return httpx.Response(200, json=_valid_result())

    monkeypatch.setattr(service.httpx, "post", fake_post)
    monkeypatch.setattr(service.settings, "ai_base_url", "http://ai-worker:8100/")

    assert service._call_ai(_request()) == _valid_result()
    assert captured["url"] == "http://ai-worker:8100/internal/v1/articles/analyze"
    assert captured["json"]["article_id"] == "101"
    assert captured["json"]["mysql_article_id"] == 101


@pytest.mark.parametrize(
    ("error", "status_code", "message"),
    [
        (
            httpx.ReadTimeout("timed out", request=httpx.Request("POST", "http://ai-worker")),
            504,
            "AI 분석 시간이 초과되었습니다.",
        ),
        (
            httpx.ConnectError("refused", request=httpx.Request("POST", "http://ai-worker")),
            503,
            "AI 분석 서비스에 연결할 수 없습니다.",
        ),
    ],
)
def test_call_ai_converts_transport_errors(monkeypatch, error, status_code, message) -> None:
    # 네트워크 라이브러리 예외가 API 전역 500으로 새지 않고 명시적 도메인 오류가 되어야 한다.
    monkeypatch.setattr(service.httpx, "post", lambda *args, **kwargs: (_ for _ in ()).throw(error))

    with pytest.raises(AppException) as raised:
        service._call_ai(_request())

    assert raised.value.status_code == status_code
    assert raised.value.code == "EXTRACTION_FAILED"
    assert raised.value.message == message


def test_call_ai_maps_worker_validation_error(monkeypatch) -> None:
    monkeypatch.setattr(
        service.httpx,
        "post",
        lambda *args, **kwargs: httpx.Response(400, json={"detail": "content is required"}),
    )

    with pytest.raises(AppException) as raised:
        service._call_ai(_request())

    assert raised.value.status_code == 400
    assert raised.value.code == "INVALID_ARTICLE"
    assert raised.value.message == "content is required"


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(500, json={"detail": "inference failed"}),
        httpx.Response(200, content=b"not-json"),
        httpx.Response(200, json={"classification": {}, "nodes": []}),
    ],
)
def test_call_ai_rejects_failed_or_invalid_worker_response(monkeypatch, response) -> None:
    # 잘못된 결과로 Neo4j 트랜잭션을 시작하지 않도록 AI 경계에서 차단한다.
    monkeypatch.setattr(service.httpx, "post", lambda *args, **kwargs: response)

    with pytest.raises(AppException) as raised:
        service._call_ai(_request())

    assert raised.value.status_code == 502
    assert raised.value.code == "EXTRACTION_FAILED"
