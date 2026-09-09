# 앱 전역 설정값. .env 파일 또는 환경 변수에서 값을 읽어온다.
from pathlib import Path

from pydantic_settings import BaseSettings

# 실행 위치(CWD)에 상관없이 항상 backend/fastapi/.env를 찾도록 이 파일 기준 절대경로로 지정
ENV_FILE_PATH = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    app_name: str = "starlight-news-ai"
    env: str = "local"
    # Spring Boot -> FastAPI 내부 호출을 검증할 때 쓰는 공유 키 (dependencies.py에서 사용)
    # TODO: 실제 값은 Spring Boot 담당자와 합의 후 .env로 관리
    internal_api_key: str = "change-me"

    # 아래 Neo4j 접속 정보는 아직 임의 기본값.
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_username: str = "neo4j"
    neo4j_password: str = "change-me"

    class Config:
        env_file = ENV_FILE_PATH


settings = Settings()
