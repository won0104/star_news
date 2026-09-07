# 여러 도메인이 공용으로 쓰는 FastAPI 의존성(Depends) 모음
from fastapi import Header, HTTPException, status

from app.config import settings


# Spring Boot -> FastAPI 내부 호출 인증. /internal/v1 라우터에서 공통으로 사용한다.
# 헤더 이름/값 방식은 Spring Boot 담당자와 합의해서 확정할 것 (현재는 임시 기본값).
def verify_internal_service(x_internal_api_key: str = Header(...)) -> None:
    if x_internal_api_key != settings.internal_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid internal api key",
        )
