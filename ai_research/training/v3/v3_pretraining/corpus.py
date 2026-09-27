"""단계 2 manifest의 PASS·기존 train Gold만 읽는 provenance 검사 경계.

이 reader는 학습/정적 감사 전용이다. runtime은 이 모듈이나 Gold 경로를 알지 않는다.
"""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Sequence

from runtime.v3_pretraining.source_layout import RawArticle
from training.v3_pretraining.targets import (R06_0_GOLD_CONTRACT,
                                             ValidatedGoldArticle,
                                             validate_gold_envelope,
                                             validate_gold_record)


REPO = Path(__file__).resolve().parents[3]
PROJECT = Path(__file__).resolve().parents[2]
DOCS = PROJECT / "docs/v3-pretraining"
SOURCE = REPO / "data/processed/gnews/gnews-1k-spring-preprocessed-v1.0.json"
SPLIT = REPO / "data/gold/v3_work/spring-preprocessed-v1/round_assignment.json"
GOLD_DIR = REPO / "gold_verified"
SCHEMA = REPO / "data/gold/schema/articlelocal-semantic-gold-v1.3.schema.json"
GUIDELINE = REPO / "data/gold/guideline/articlelocal-semantic-guideline-r05.3.md"
R06_SCHEMA = REPO / "data/gold/schema/articlelocal-semantic-gold-v1.4.schema.json"
R06_GUIDELINE = REPO / "data/gold/guideline/articlelocal-semantic-guideline-r06.0.md"


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


class ProvisionalGoldReader:
    """Frozen 499-article manifest reader with explicit train/dev/test boundaries."""

    def __init__(self, manifest_path: str | Path) -> None:
        self.manifest_path = Path(manifest_path)
        manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        required = {"schema_version", "run_mode", "created_from_head", "source",
                    "original_split", "schema", "guideline", "source_join",
                    "expected_counts", "selected_count", "articles", "excluded"}
        if set(manifest) != required or manifest["schema_version"] != "v3-provisional-split-v1" or manifest["run_mode"] != "PROVISIONAL_TRAINED_INTEGRATION":
            raise ValueError("provisional split manifest schema/mode differs")
        paths = ((SOURCE, manifest["source"]), (SPLIT, manifest["original_split"]),
                 (SCHEMA, manifest["schema"]), (GUIDELINE, manifest["guideline"]),
                 (DOCS / "source-join-manifest.json", manifest["source_join"]))
        if any(str(path.resolve()) != row["path"] or _digest(path) != row["sha256"]
               for path, row in paths):
            raise ValueError("provisional split source/schema/guideline hash drift")
        if manifest["expected_counts"] != {"train": 400, "dev": 50, "test": 49} or manifest["selected_count"] != 499:
            raise ValueError("provisional split cardinality contract differs")
        self.rows = {row["article_id"]: row for row in manifest["articles"]}
        if len(self.rows) != 499 or len(manifest["articles"]) != 499:
            raise ValueError("provisional split has duplicate or missing article IDs")
        counts = {split: sum(row["split"] == split for row in self.rows.values())
                  for split in ("train", "dev", "test")}
        if counts != manifest["expected_counts"] or any(
                set(row) != {"article_id", "split", "source_sha256", "gold_file", "gold_sha256"}
                or row["split"] not in counts for row in self.rows.values()):
            raise ValueError("provisional split rows/counts differ")
        if manifest["excluded"] != [{"article_id": "GNEWS-16483dcf7e12279c6e2333af4e335fa7",
                                      "split": "dev", "gold_file": "136.json",
                                      "reason": "TM6: interval granularity/order mismatch"}]:
            raise ValueError("provisional split quarantine contract differs")
        source_rows = json.loads(SOURCE.read_text(encoding="utf-8"))["articles"]
        self.source = {row["article_id"]: row for row in source_rows}
        self.manifest = manifest
        # Selection integrity consumes this monotonic ledger.  A test read cannot
        # later be hidden by passing an unrelated evaluation input to the runner.
        self._access_counts = {"train": 0, "dev": 0, "test": 0}

    def ids(self, split: str) -> tuple[str, ...]:
        if split not in ("train", "dev", "test"):
            raise ValueError("known provisional split required")
        return tuple(row["article_id"] for row in self.manifest["articles"]
                     if row["split"] == split)

    def access_count(self, split: str) -> int:
        """Return the monotonic successful/attempted article-read count by split."""
        if split not in self._access_counts:
            raise ValueError("known provisional split required")
        return self._access_counts[split]

    def load(self, ids: Sequence[str], *, split: str) -> tuple[ValidatedGoldArticle, ...]:
        requested = tuple(ids)
        if split not in ("train", "dev", "test") or len(set(requested)) != len(requested):
            raise ValueError("provisional load needs one explicit split and unique IDs")
        self._access_counts[split] += len(requested)
        output = []
        for aid in requested:
            row = self.rows.get(aid)
            if row is None or row["split"] != split:
                raise ValueError(f"{aid}: provisional split boundary mismatch")
            source = self.source.get(aid)
            if source is None or sha256(source["article"].encode("utf-8")).hexdigest() != row["source_sha256"]:
                raise ValueError(f"{aid}: provisional source changed")
            path = GOLD_DIR / row["gold_file"]
            if _digest(path) != row["gold_sha256"]:
                raise ValueError(f"{aid}: provisional Gold changed")
            gold_rows = json.loads(path.read_text(encoding="utf-8"))["articles"]
            gold = next((item for item in gold_rows if item["article_id"] == aid), None)
            if gold is None:
                raise ValueError(f"{aid}: Gold envelope lacks provisional article")
            raw = RawArticle(aid, f"{aid}:{row['source_sha256'][:16]}", source["article"],
                             row["source_sha256"], source.get("published"))
            article = (ValidatedGoldArticle.from_record(raw, gold, split="train")
                       if split == "train" else
                       ValidatedGoldArticle.from_evaluation_record(raw, gold, split=split))
            output.append(article)
        return tuple(output)


class R06GoldReader:
    """Merged v1.4/r06.0 Gold를 source와 frozen split에 결합하는 reader.

    ``validate_inventory``는 intake 정적 검증이고, ``load``만 compiler/evaluation
    access ledger를 증가시킨다. legacy reader의 manifest/hash 권한은 참조하지도
    변경하지도 않는다.
    """

    def __init__(self, gold_path: str | Path, *, source_path: str | Path = SOURCE,
                 split_path: str | Path = SPLIT) -> None:
        self.gold_path = Path(gold_path)
        self.source_path = Path(source_path)
        self.split_path = Path(split_path)
        envelope = json.loads(self.gold_path.read_text(encoding="utf-8"))
        if (set(envelope) != {"version", "guideline_version", "articles"}
                or envelope["version"] != R06_0_GOLD_CONTRACT.version
                or envelope["guideline_version"] != R06_0_GOLD_CONTRACT.guideline_version
                or not isinstance(envelope["articles"], list)):
            raise ValueError("r06 Gold envelope version/guideline/fields differ")
        validate_gold_envelope(envelope, contract=R06_0_GOLD_CONTRACT)
        article_ids = [row.get("article_id") for row in envelope["articles"]
                       if isinstance(row, dict)]
        if (len(article_ids) != len(envelope["articles"])
                or any(not isinstance(value, str) or not value for value in article_ids)
                or len(set(article_ids)) != len(article_ids)):
            raise ValueError("r06 Gold needs unique non-empty article IDs")
        self.gold = {row["article_id"]: row for row in envelope["articles"]}

        source_payload = json.loads(self.source_path.read_text(encoding="utf-8"))
        source_ids = [row.get("article_id") for row in source_payload.get("articles", [])]
        if (len(source_ids) != len(set(source_ids))
                or any(not isinstance(value, str) or not value for value in source_ids)):
            raise ValueError("processed source has duplicate/invalid article IDs")
        self.source = {row["article_id"]: row for row in source_payload["articles"]}

        assignment = json.loads(self.split_path.read_text(encoding="utf-8"))
        membership_rows = [(article_id, round_row["split"])
                           for round_row in assignment["rounds"]
                           for article_id in round_row["article_ids"]]
        if len({article_id for article_id, _split in membership_rows}) != len(membership_rows):
            raise ValueError("split manifest assigns an article more than once")
        self.membership = dict(membership_rows)
        if any(split not in ("train", "dev", "test")
               for split in self.membership.values()):
            raise ValueError("split manifest contains an unknown split")
        self._access_counts = {"train": 0, "dev": 0, "test": 0}
        self._static_validation_counts = {"train": 0, "dev": 0, "test": 0}

    def _raw(self, article_id: str) -> RawArticle:
        source = self.source.get(article_id)
        if source is None:
            raise ValueError(f"{article_id}: processed source row missing")
        content = source["article"]
        digest = sha256(content.encode("utf-8")).hexdigest()
        return RawArticle(article_id, f"{article_id}:r06:{digest[:16]}", content,
                          digest, source.get("published"))

    def validate_inventory(self) -> tuple[str, ...]:
        """Merged artifact 전부를 schema/source/split/hard invariant로 검증한다."""
        counts = {"train": 0, "dev": 0, "test": 0}
        for article_id, gold in self.gold.items():
            split = self.membership.get(article_id)
            if split is None:
                raise ValueError(f"{article_id}: split manifest row missing")
            raw = self._raw(article_id)
            validate_gold_record(raw, gold, contract=R06_0_GOLD_CONTRACT)
            counts[split] += 1
        self._static_validation_counts = counts
        return tuple(self.gold)

    def load(self, ids: Sequence[str], *, split: str) -> tuple[ValidatedGoldArticle, ...]:
        """명시된 split의 r06 article만 ValidatedGoldArticle로 만든다."""
        requested = tuple(ids)
        if split not in self._access_counts or len(set(requested)) != len(requested):
            raise ValueError("r06 load needs one explicit split and unique IDs")
        self._access_counts[split] += len(requested)
        output = []
        for article_id in requested:
            if self.membership.get(article_id) != split:
                raise ValueError(f"{article_id}: r06 split boundary mismatch")
            gold = self.gold.get(article_id)
            if gold is None:
                raise ValueError(f"{article_id}: r06 Gold row missing")
            raw = self._raw(article_id)
            article = (ValidatedGoldArticle.from_record(
                raw, gold, split="train", contract=R06_0_GOLD_CONTRACT)
                if split == "train" else
                ValidatedGoldArticle.from_evaluation_record(
                    raw, gold, split=split, contract=R06_0_GOLD_CONTRACT))
            output.append(article)
        return tuple(output)

    def access_count(self, split: str) -> int:
        if split not in self._access_counts:
            raise ValueError("known r06 split required")
        return self._access_counts[split]

    @property
    def static_validation_counts(self) -> dict[str, int]:
        return dict(self._static_validation_counts)
