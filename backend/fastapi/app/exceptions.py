# 앱 전역 예외 클래스 + 예외 -> HTTP 응답 변환 핸들러 모음
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from neo4j.exceptions import ServiceUnavailable


# main.py의 핸들러가 status_code/code/message를 응답에 사용한다.
class AppException(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(message)


# 요청 검증 실패(400)/그 외 예상 못 한 실패(500)는 엔드포인트별로 에러 코드가 달라서 경로로 구분한다 (API 명세 기준)
_VALIDATION_CODE_BY_PATH = {
    "/internal/v1/articles/analyze": "INVALID_ARTICLE",
    "/internal/v1/recommendations/calculate": "INVALID_RECOMMENDATION_REQUEST",
    "/internal/v1/user-graph/sync": "INVALID_USER_GRAPH_SYNC_REQUEST",
}
_FAILURE_CODE_BY_PATH = {
    "/internal/v1/articles/analyze": "EXTRACTION_FAILED",
    "/internal/v1/recommendations/calculate": "RECOMMENDATION_CALCULATION_FAILED",
    "/internal/v1/user-graph/sync": "USER_GRAPH_SYNC_FAILED",
}


def _error_body(code: str, message: str) -> dict:
    return {"code": code, "message": message}


# main.py에서 app 생성 직후 한 번 호출해서 핸들러를 등록한다.
def register_exception_handlers(app: FastAPI) -> None:
    # 서비스/repository에서 의도적으로 raise한 에러 (404, 409 등)
    @app.exception_handler(AppException)
    async def handle_app_exception(request: Request, exc: AppException) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=_error_body(exc.code, exc.message))

    # Pydantic 요청 스키마 검증 실패
    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        code = _VALIDATION_CODE_BY_PATH.get(request.url.path, "INVALID_REQUEST")
        return JSONResponse(status_code=400, content=_error_body(code, "요청 형식이 올바르지 않습니다."))

    # Neo4j 서버 자체에 연결이 안 될 때
    @app.exception_handler(ServiceUnavailable)
    async def handle_neo4j_unavailable(request: Request, exc: ServiceUnavailable) -> JSONResponse:
        return JSONResponse(status_code=503, content=_error_body("NEO4J_UNAVAILABLE", "Neo4j에 연결할 수 없습니다."))

    # 그 외 예상하지 못한 모든 오류 (최후 방어선)
    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        code = _FAILURE_CODE_BY_PATH.get(request.url.path, "INTERNAL_ERROR")
        return JSONResponse(status_code=500, content=_error_body(code, "예상하지 못한 오류가 발생했습니다."))
