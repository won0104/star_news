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

    # 모델은 별도 상주 컨테이너가 소유하고, 이 앱은 내부 HTTP로만 추론을 요청한다.
    ai_base_url: str = "http://ai-worker:8100"
    # CPU 추론은 V1기준 평균 20~30초 정도, V2기준 40~200초 걸리기 때문에 150초 타임아웃 적용.
    # 다만 V2는 응답(성능) 개선이 매우매우 필요하므로, 성능 개선이 이루어지기 전까지는 사용하지 않을 예정임. (shit)
    ai_connect_timeout_seconds: float = 3.0
    ai_request_timeout_seconds: float = 150.0

    class Config:
        # 실제 .env와 연결
        env_file = ENV_FILE_PATH


settings = Settings()
