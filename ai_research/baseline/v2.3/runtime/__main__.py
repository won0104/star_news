"""기본 pinned v2.2 compact Article-local KG CLI."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .eventframe.contracts import RuntimeContractError, RuntimeConfigurationError
from .pipeline import ArticleLocalKGPipeline


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Gold-free Article-local KG inference")
    parser.add_argument("--config", help="Pinned pipeline config (default: v2.2 compact)")
    parser.add_argument("--input", required=True, help="One Article JSON object")
    parser.add_argument("--output", required=True, help="Canonical KG JSON output")
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--profile", choices=("PUBLIC", "AUDIT", "DEBUG"), default="PUBLIC")
    parser.add_argument("--debug-trace", action="store_true")
    parser.add_argument("--pretty", action="store_true", help="Include canonical graph view")
    args = parser.parse_args()
    output = Path(args.output)
    try:
        pipeline = ArticleLocalKGPipeline.from_config(args.config, device=args.device)
        article = json.loads(Path(args.input).read_text(encoding="utf-8"))
        result = pipeline.run(
            article, output_profile=args.profile, debug_trace=args.debug_trace,
        )
        payload = result.to_dict()
        if args.pretty:
            if not hasattr(result, "pretty"):
                raise RuntimeConfigurationError(
                    "--pretty requires the v2.2 compact PUBLIC graph"
                )
            payload["pretty"] = result.pretty()
        return_code = 0
    except Exception as error:
        category = (
            error.category
            if isinstance(error, RuntimeContractError)
            else "COMPONENT_RUNTIME_ERROR"
        )
        payload = {
            "status": "ERROR",
            "error": {"category": category, "message": str(error)},
        }
        return_code = 2
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
