# 앱 전역에서 공용으로 쓰는 예외 클래스 모음
class AppException(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)
