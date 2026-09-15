"""Build Neo4j offline bundle from SSAFY CSV via GPU/CPU analyze.

Example (local GPU, 10 smoke):
  set PYTHONPATH=ai
  set STARLIGHT_AI_DEVICE=auto
  python -m starlight_ai.cli_batch ^
    --csv "...\\ssafy_dataset_news_2024_1st_half.csv" ^
    --limit 10 ^
    --kg-dir "...\\artifacts\\kg-extractor" ^
    --hf-cache "...\\.cache\\huggingface\\hub" ^
    --out ai\\outputs\\neo4j_bundle_10
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
from pathlib import Path

_AI_ROOT = Path(__file__).resolve().parent.parent
if str(_AI_ROOT) not in sys.path:
    sys.path.insert(0, str(_AI_ROOT))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--kg-dir", default=os.environ.get("KG_MODEL_DIR"))
    parser.add_argument(
        "--hf-cache",
        default=os.environ.get("ARTICLELOCAL_HF_CACHE")
        or os.environ.get("HF_HUB_CACHE"),
    )
    parser.add_argument("--device", default=os.environ.get("STARLIGHT_AI_DEVICE", "auto"))
    parser.add_argument("--mysql-id-start", type=int, default=1)
    parser.add_argument("--no-stratified", action="store_true")
    parser.add_argument("--no-publisher", action="store_true")
    parser.add_argument("--online", action="store_true")
    parser.add_argument(
        "--save-raw",
        action="store_true",
        help="also write per-article JSON under out/raw/",
    )
    args = parser.parse_args(argv)

    if not args.kg_dir or not args.hf_cache:
        parser.error("--kg-dir and --hf-cache (or env) are required")
    if not args.csv.is_file():
        parser.error(f"CSV not found: {args.csv}")

    if not args.online:
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    os.environ["TOKENIZERS_PARALLELISM"] = "false"

    from starlight_ai.batch.csv_sample import sample_articles
    from starlight_ai.batch.neo4j_bundle import Neo4jBundleBuilder
    from starlight_ai.pipeline import ArticleAnalyzer

    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    raw_dir = out / "raw"
    if args.save_raw:
        raw_dir.mkdir(parents=True, exist_ok=True)

    checkpoint_path = out / "checkpoint.json"
    done_ids: set[str] = set()
    if checkpoint_path.is_file():
        cp = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        done_ids = set(cp.get("done_article_ids") or [])

    print(f"Sampling up to {args.limit} articles from {args.csv} ...", flush=True)
    articles = sample_articles(
        args.csv,
        args.limit,
        stratified=not args.no_stratified,
        mysql_id_start=args.mysql_id_start,
    )
    print(f"Sampled {len(articles)} articles (checkpoint done={len(done_ids)})", flush=True)

    analyzer = ArticleAnalyzer(
        device=args.device,
        kg_dir=args.kg_dir,
        hf_cache=args.hf_cache,
        local_files_only=not args.online,
        include_classified_as_edge=False,
    )
    bundle = Neo4jBundleBuilder(with_publisher=not args.no_publisher)

    # If resuming, rebuild bundle from saved raw if present.
    if done_ids and args.save_raw and raw_dir.is_dir():
        for p in sorted(raw_dir.glob("*.json")):
            try:
                bundle.add_result(json.loads(p.read_text(encoding="utf-8")))
            except Exception:
                pass

    timings: list[float] = []
    errors: list[dict[str, str]] = []
    t0 = time.perf_counter()

    for i, article in enumerate(articles, 1):
        aid = article["article_id"]
        if aid in done_ids:
            continue
        started = time.perf_counter()
        try:
            result = analyzer.process(article)
            elapsed = time.perf_counter() - started
            timings.append(elapsed)
            result["meta"] = {
                **(result.get("meta") or {}),
                "elapsed_seconds": round(elapsed, 3),
                "device": analyzer.device,
            }
            bundle.add_result(result)
            if args.save_raw:
                (raw_dir / f"{article['mysql_article_id']}_{aid[:12]}.json").write_text(
                    json.dumps(result, ensure_ascii=False),
                    encoding="utf-8",
                )
            done_ids.add(aid)
        except Exception as exc:
            errors.append({"article_id": aid, "error": str(exc)})
            traceback.print_exc()
            print(f"[{i}/{len(articles)}] FAIL {aid}: {exc}", flush=True)
            continue

        checkpoint_path.write_text(
            json.dumps(
                {
                    "done_article_ids": sorted(done_ids),
                    "errors": errors,
                    "count_done": len(done_ids),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        if i == 1 or i % 10 == 0 or i == len(articles):
            avg = sum(timings) / len(timings) if timings else 0
            print(
                f"[{i}/{len(articles)}] ok avg={avg:.2f}s last={timings[-1]:.2f}s "
                f"device={analyzer.device}",
                flush=True,
            )

    summary = bundle.write(out)
    wall = time.perf_counter() - t0
    manifest = {
        "csv": str(args.csv),
        "limit": args.limit,
        "sampled": len(articles),
        "done": len(done_ids),
        "errors": len(errors),
        "device": analyzer.device,
        "embedding_model": analyzer.embedding_model,
        "embedding_dim": 1024,
        "vector_index_note": "server V2 must be 1024-d (KURE-v1)",
        "wall_seconds": round(wall, 2),
        "avg_seconds_per_article": round(sum(timings) / len(timings), 3) if timings else None,
        "timings_seconds": [round(x, 3) for x in timings],
        "bundle": summary,
        "error_samples": errors[:20],
    }
    (out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(
        f"Done. done={len(done_ids)} errors={len(errors)} "
        f"wall={wall:.1f}s -> {out}",
        flush=True,
    )
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
