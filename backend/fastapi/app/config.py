# 앱 전역 설정값. .env 파일 또는 환경 변수에서 값을 읽어온다.
from pathlib import Path

from pydantic_settings import BaseSettings

# 실행 위치(CWD)에 상관없이 항상 backend/fastapi/.env를 찾도록 이 파일 기준 절대경로로 지정
ENV_FILE_PATH = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    app_name: str = "starlight-news-ai"
    env: str = "local"
    # Spring Boot -> FastAPI 내부 호출을 검증할 때 쓰는 공유 키 (dependencies.py에서 사용)
    internal_api_key: str

    # Neo4j 접속 정보
    neo4j_uri: str
    neo4j_username: str
    neo4j_password: str

    class Config:
        # 실제 .env와 연결
        env_file = ENV_FILE_PATH


settings = Settings()
