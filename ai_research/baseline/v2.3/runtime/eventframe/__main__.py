"""Raw EventFrame result의 명시적 legacy compatibility CLI."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .contracts import RuntimeContractError
from .runtime import ArticleLocalRuntime


def main() -> int:
    parser = argparse.ArgumentParser(description="Run legacy raw EventFrame compatibility inference")
    parser.add_argument("--config", required=True)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--debug-trace", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    output = Path(args.output)
    try:
        runtime = ArticleLocalRuntime.from_config(args.config, device=args.device)
        article = json.loads(Path(args.input).read_text(encoding="utf-8"))
        result = runtime.run(article, debug_trace=args.debug_trace)
        payload = result.to_dict()
        if args.pretty:
            payload["pretty"] = result.pretty()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        return 0
    except Exception as error:
        category = (
            error.category
            if isinstance(error, RuntimeContractError)
            else "COMPONENT_RUNTIME_ERROR"
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(
                {"status": "ERROR", "error": {"category": category, "message": str(error)}},
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
