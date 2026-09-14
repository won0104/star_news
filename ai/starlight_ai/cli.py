"""CLI smoke: one article -> schema JSON.

Local GPU example:
  set STARLIGHT_AI_DEVICE=auto
  python -m starlight_ai.cli --kg-dir ... --hf-cache ... --input article.json

Server CPU:
  set STARLIGHT_AI_DEVICE=cpu
  (same, with /models paths)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

# Make `ai/` importable when run as module from repo.
_AI_ROOT = Path(__file__).resolve().parent.parent
if str(_AI_ROOT) not in sys.path:
    sys.path.insert(0, str(_AI_ROOT))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--kg-dir", default=os.environ.get("KG_MODEL_DIR"))
    parser.add_argument(
        "--hf-cache",
        default=os.environ.get("ARTICLELOCAL_HF_CACHE")
        or os.environ.get("HF_HUB_CACHE"),
    )
    parser.add_argument(
        "--device",
        default=os.environ.get("STARLIGHT_AI_DEVICE", "auto"),
        help="cpu | cuda | auto (server: force cpu)",
    )
    parser.add_argument("--skip-classify", action="store_true")
    parser.add_argument("--skip-embed", action="store_true")
    parser.add_argument("--online", action="store_true", help="allow HF download")
    args = parser.parse_args(argv)

    if not args.kg_dir or not args.hf_cache:
        parser.error("--kg-dir and --hf-cache (or env KG_MODEL_DIR / ARTICLELOCAL_HF_CACHE) required")

    # Offline by default for server parity; local --online to fill cache.
    if not args.online:
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    os.environ["TOKENIZERS_PARALLELISM"] = "false"

    from starlight_ai.pipeline import ArticleAnalyzer

    article = json.loads(args.input.read_text(encoding="utf-8-sig"))
    analyzer = ArticleAnalyzer(
        device=args.device,
        kg_dir=args.kg_dir,
        hf_cache=args.hf_cache,
        local_files_only=not args.online,
        enable_classification=not args.skip_classify,
        enable_embedding=not args.skip_embed,
    )
    started = time.perf_counter()
    result = analyzer.process(article)
    result["meta"]["device"] = analyzer.device
    result["meta"]["elapsed_seconds"] = round(time.perf_counter() - started, 2)

    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
        print(f"Wrote {args.output} status={result.get('status')} device={analyzer.device}")
    else:
        print(text)
    return 0 if result.get("status") in {"OK", "PARTIAL"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
