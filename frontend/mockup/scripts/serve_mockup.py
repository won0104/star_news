"""별빛 뉴스 정적 파일과 History API fallback을 제공하는 로컬 개발 서버."""

from __future__ import annotations

import argparse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class SpaRequestHandler(SimpleHTTPRequestHandler):
    """실제 파일이 아닌 화면 경로 요청에는 index.html을 반환합니다."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(PROJECT_ROOT), **kwargs)

    def do_GET(self) -> None:  # noqa: N802 - 표준 라이브러리 메서드 이름
        parsed = urlsplit(self.path)
        relative_path = parsed.path.lstrip("/")
        requested_path = (PROJECT_ROOT / relative_path).resolve()

        try:
            requested_path.relative_to(PROJECT_ROOT)
            is_inside_project = True
        except ValueError:
            is_inside_project = False

        is_asset_request = Path(parsed.path).suffix != ""
        if is_inside_project and not requested_path.is_file() and not is_asset_request:
            self.path = "/index.html"

        super().do_GET()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="별빛 뉴스 웹 목업 서버")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=4173)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    server = ThreadingHTTPServer((args.host, args.port), SpaRequestHandler)
    print(f"별빛 뉴스 목업: http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
