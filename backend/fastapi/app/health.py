# Docker Compose / Spring Boot가 컨테이너 기동 상태를 확인하는 헬스체크. 인증 없이 접근 가능.
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def check_health() -> dict[str, str]:
    return {"status": "ok"}
