"""단계 2 manifest의 PASS·기존 train Gold만 읽는 provenance 검사 경계.

이 reader는 학습/정적 감사 전용이다. runtime은 이 모듈이나 Gold 경로를 알지 않는다.
"""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Sequence

from runtime.v3_pretraining.source_layout import RawArticle
from training.v3_pretraining.targets import ValidatedGoldArticle


REPO = Path(__file__).resolve().parents[3]
PROJECT = Path(__file__).resolve().parents[2]
DOCS = PROJECT / "docs/v3-pretraining"
SOURCE = REPO / "data/processed/gnews/gnews-1k-spring-preprocessed-v1.0.json"
SPLIT = REPO / "data/gold/v3_work/spring-preprocessed-v1/round_assignment.json"
GOLD_DIR = REPO / "gold_verified"


def _digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


class TrainGoldReader:
    """현재 verified train Gold만 반환하고 입력 drift·split 누출은 즉시 실패시킨다."""

    def __init__(self) -> None:
        join = json.loads((DOCS / "source-join-manifest.json").read_text(encoding="utf-8"))
        selection = json.loads((DOCS / "engineering50-manifest.json").read_text(encoding="utf-8"))
        if _digest(SOURCE) != join["processed_sha256"] or _digest(SPLIT) != join["split_manifest_sha256"]:
            raise ValueError("processed/split bytes changed since Gold intake")
        if selection["split_manifest_sha256"] != join["split_manifest_sha256"]:
            raise ValueError("engineering subset uses another split manifest")
        self.source = {row["article_id"]: row for row in json.loads(SOURCE.read_text(encoding="utf-8"))["articles"]}
        self.rows = {row["article_id"]: row for row in join["rows"]}
        if len(self.rows) != len(join["rows"]):
            raise ValueError("duplicate source-join article ID")
        assignment = json.loads(SPLIT.read_text(encoding="utf-8"))
        self.membership = {article_id: round_row["split"] for round_row in assignment["rounds"]
                           for article_id in round_row["article_ids"]}
        self.engineering_ids = tuple(row["article_id"] for row in selection["articles"])
        if len(self.engineering_ids) != 50 or len(set(self.engineering_ids)) != 50:
            raise ValueError("engineering50 manifest has wrong cardinality")
        if any(self.membership.get(aid) != "train" for aid in self.engineering_ids):
            raise ValueError("engineering50 contains non-train article")

    def load(self, ids: Sequence[str] | None = None) -> tuple[ValidatedGoldArticle, ...]:
        requested = tuple(ids) if ids is not None else self.engineering_ids
        if len(set(requested)) != len(requested):
            raise ValueError("duplicate requested article ID")
        output = []
        for aid in requested:
            row = self.rows.get(aid)
            if row is None or row["validation_status"] != "PASS" or row["split"] != "train" or self.membership.get(aid) != "train":
                raise ValueError(f"{aid}: current verified train Gold required")
            source = self.source[aid]
            if sha256(source["article"].encode("utf-8")).hexdigest() != row["source_sha256"]:
                raise ValueError(f"{aid}: source content changed")
            path = GOLD_DIR / row["gold_file"]
            if _digest(path) != row["gold_file_sha256"]:
                raise ValueError(f"{aid}: Gold file changed")
            gold_rows = json.loads(path.read_text(encoding="utf-8"))["articles"]
            gold = next((item for item in gold_rows if item["article_id"] == aid), None)
            if gold is None:
                raise ValueError(f"{aid}: Gold envelope lacks joined article")
            raw = RawArticle(aid, f"{aid}:{row['source_sha256'][:16]}", source["article"],
                             row["source_sha256"], source.get("published"))
            output.append(ValidatedGoldArticle.from_record(raw, gold, split="train"))
        return tuple(output)

    def all_valid_train_ids(self) -> tuple[str, ...]:
        return tuple(row["article_id"] for row in self.rows.values()
                     if row["split"] == "train" and row["validation_status"] == "PASS"
                     and self.membership.get(row["article_id"]) == "train")
