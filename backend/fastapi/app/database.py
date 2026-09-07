# Neo4j 연결 설정. 도메인별 repository.py에서 get_neo4j_session을 의존성으로 주입받아 사용한다.
from collections.abc import Generator

from neo4j import Driver, GraphDatabase, Session

from app.config import settings

_driver: Driver = GraphDatabase.driver(
    settings.neo4j_uri,
    auth=(settings.neo4j_username, settings.neo4j_password),
)


def get_neo4j_session() -> Generator[Session, None, None]:
    with _driver.session() as session:
        yield session
