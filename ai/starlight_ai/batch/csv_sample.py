"""Sample SSAFY news CSV without loading the full corpus."""

from __future__ import annotations

import csv
import hashlib
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterator


def _row_to_article(row: dict[str, str], *, mysql_article_id: int | None = None) -> dict[str, Any]:
    link = (row.get("link") or "").strip()
    title = (row.get("title") or "").strip()
    body = (row.get("article") or "").strip()
    published = (row.get("published") or "").strip()
    company = (row.get("company") or "").strip()
    category = (row.get("category_str") or row.get("category") or "").strip()
    aid = hashlib.sha1((link or f"{company}|{title}|{published}").encode("utf-8")).hexdigest()
    out: dict[str, Any] = {
        "article_id": aid,
        "title": title,
        "content": body,
        "published_at": published,
        "source": company,
        "url": link,
        "category": category,
    }
    if mysql_article_id is not None:
        out["mysql_article_id"] = mysql_article_id
    return out


def iter_csv_rows(path: Path | str) -> Iterator[dict[str, str]]:
    path = Path(path)
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as f:
        reader = csv.DictReader(f, delimiter="|")
        for row in reader:
            if not (row.get("article") or "").strip() and not (row.get("title") or "").strip():
                continue
            yield row


def sample_articles(
    path: Path | str,
    limit: int,
    *,
    stratified: bool = True,
    mysql_id_start: int = 1,
) -> list[dict[str, Any]]:
    """Return up to ``limit`` articles. Stratified by YYYY-MM when possible."""
    path = Path(path)
    if limit <= 0:
        raise ValueError("limit must be positive")

    if not stratified:
        rows: list[dict[str, str]] = []
        for row in iter_csv_rows(path):
            rows.append(row)
            if len(rows) >= limit:
                break
    else:
        rows = _stratified_rows(path, limit)

    articles: list[dict[str, Any]] = []
    seen: set[str] = set()
    mysql_id = mysql_id_start
    for row in rows:
        art = _row_to_article(row, mysql_article_id=mysql_id)
        if art["article_id"] in seen:
            continue
        seen.add(art["article_id"])
        articles.append(art)
        mysql_id += 1
        if len(articles) >= limit:
            break
    return articles


def _stratified_rows(path: Path, limit: int) -> list[dict[str, str]]:
    month_counts: dict[str, int] = defaultdict(int)
    for row in iter_csv_rows(path):
        published = (row.get("published") or "")[:7]
        key = published if len(published) == 7 else "unknown"
        month_counts[key] += 1

    keys = sorted(month_counts.keys())
    if not keys:
        return []
    per = max(1, limit // len(keys))
    remaining = {k: per for k in keys}
    leftover = limit - per * len(keys)
    if leftover > 0 and keys:
        remaining[keys[0]] += leftover

    picked: list[dict[str, str]] = []
    for row in iter_csv_rows(path):
        if len(picked) >= limit:
            break
        published = (row.get("published") or "")[:7]
        key = published if len(published) == 7 else "unknown"
        if remaining.get(key, 0) <= 0:
            continue
        remaining[key] -= 1
        picked.append(row)
    return picked
