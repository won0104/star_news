from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "starlight-news-ai"
    env: str = "local"

    class Config:
        env_file = ".env"


settings = Settings()
