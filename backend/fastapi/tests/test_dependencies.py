"""내부 API 키 검증 의존성 단위 테스트. Neo4j 없이 돈다(`pytest --noconftest` 로도 실행 가능)."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.config import settings
from app.dependencies import verify_internal_service


def test_same_key_passes() -> None:
    verify_internal_service(settings.internal_api_key)


def test_different_key_is_rejected_with_401() -> None:
    with pytest.raises(HTTPException) as exc_info:
        verify_internal_service(settings.internal_api_key + "x")

    assert exc_info.value.status_code == 401


def test_non_ascii_key_is_rejected_with_401_not_500() -> None:
    # str 끼리 hmac.compare_digest 를 쓰면 ASCII 가 아닌 글자에서 TypeError 가 난다.
    with pytest.raises(HTTPException) as exc_info:
        verify_internal_service("키-" + settings.internal_api_key)

    assert exc_info.value.status_code == 401
