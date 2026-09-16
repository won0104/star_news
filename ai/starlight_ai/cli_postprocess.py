"""Postprocess Neo4j offline bundle (noise filter + entity/event dedup).

Example:
  cd ai
  set PYTHONPATH=.
  python -m starlight_ai.cli_postprocess --bundle outputs/neo4j_bundle_1000
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_AI_ROOT = Path(__file__).resolve().parent.parent
if str(_AI_ROOT) not in sys.path:
    sys.path.insert(0, str(_AI_ROOT))

from starlight_ai.batch.postprocess import postprocess_bundle


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--bundle", type=Path, required=True, help="bundle directory")
    p.add_argument("--event-threshold", type=float, default=0.92)
    p.add_argument("--event-top-k", type=int, default=8)
    p.add_argument("--no-backup", action="store_true", help="skip nodes.raw.jsonl backup")
    args = p.parse_args(argv)

    report = postprocess_bundle(
        args.bundle,
        event_threshold=args.event_threshold,
        event_top_k=args.event_top_k,
        backup=not args.no_backup,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
