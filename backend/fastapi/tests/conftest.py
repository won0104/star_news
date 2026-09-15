"""CI / 로컬 통합 테스트용. Neo4j 가 없으면 해당 테스트를 스킵한다."""

from __future__ import annotations

import pytest
from neo4j.exceptions import Neo4jError, ServiceUnavailable

from app.database import _driver


@pytest.fixture(scope="session", autouse=True)
def require_neo4j() -> None:
    try:
        with _driver.session() as session:
            session.run("RETURN 1 AS ok").consume()
    except (ServiceUnavailable, Neo4jError, OSError) as exc:
        pytest.skip(f"Neo4j unavailable for integration tests: {exc}")
