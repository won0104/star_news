# 여러 도메인이 공용으로 쓰는 FastAPI 의존성(Depends) 모음
import hmac

from fastapi import Header, HTTPException, status

from app.config import settings


# Spring Boot -> FastAPI 내부 호출 인증. /internal/v1 라우터에서 공통으로 사용한다.
# 헤더 이름/값 방식은 Spring Boot 담당자와 합의해서 확정할 것 (현재는 임시 기본값).
def verify_internal_service(x_internal_api_key: str = Header(...)) -> None:
    # `!=` 는 앞에서부터 비교하다 다른 글자에서 바로 멈춰, 응답 시간 차이로 키를 한 글자씩
    # 맞혀 볼 여지가 생긴다. compare_digest 는 길이가 같으면 끝까지 비교해 시간이 일정하다.
    # str 끼리 비교하면 ASCII 가 아닌 글자에서 TypeError(500)가 나므로 bytes 로 바꿔 비교한다.
    if not hmac.compare_digest(
        x_internal_api_key.encode("utf-8"),
        settings.internal_api_key.encode("utf-8"),
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid internal api key",
        )
