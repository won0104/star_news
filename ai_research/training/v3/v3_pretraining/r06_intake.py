"""r06.0 merged Gold와 annotation bank의 optimizer-free intake/preflight 도구.

annotation bank는 training authority가 아니다. 이 모듈은 고정된 소수 train 기사에
한해 원 verdict를 보존한 ``PROVISIONAL_ENGINEERING_ONLY`` authority를 만들며,
Gold 보호 위반·source drift·미승인 PARTICIPANT 음성은 fail-closed한다.
"""

from __future__ import annotations

from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Mapping, Sequence

from training.v3_pretraining.negative_authority import (
    SCHEMA_VERSION as AUTHORITY_SCHEMA_VERSION,
    ReviewedNegativeAuthority,
)
from training.v3_pretraining.targets import ArticleTargets, ValidatedGoldArticle


ANNOTATION_BANK_SCHEMA_VERSION = "articlelocal-extraction-sidecar-v1.0"
ANNOTATION_BANK_USAGE = "ANNOTATION_BANK_NOT_TRAINING_EXPORT"
ANNOTATION_BANK_GUIDELINE_VERSION = "articlelocal-extraction-sidecar-guideline-r01.0"
ENGINEERING_AUTHORITY_STATUS = "PROVISIONAL_ENGINEERING_ONLY"
ENGINEERING_PURPOSE = "R06_6_ARTICLE_32_STEP_ENGINEERING_REHEARSAL"
PROJECTION_POLICY_VERSION = "r06-annotation-bank-to-reviewed-authority-v1"
FIXED_PREFLIGHT_IDS = (
    "GNEWS-4ea3d0f0a2f9c9ce2fd1f0bb55e529d4",
    "GNEWS-869bada58cff05b448b889a73f44077d",
    "GNEWS-9dcd95d3d0e7c8cb3e20637d687bbfa0",
    "GNEWS-d198d950b0d1e7a5ad97e935c583441e",
    "GNEWS-8b2e87a65c0bf1dd6a31814821183f71",
    "GNEWS-ff2340162ea1e8047912b13e09293eff",
)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def file_sha256(path: str | Path) -> str:
    return sha256(Path(path).read_bytes()).hexdigest()


def canonical_sha256(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":")).encode("utf-8")
    return sha256(payload).hexdigest()


def normalized_time_form(value: object) -> str:
    """Gold allowlist의 값을 의미 확장 없이 serialization 형태로만 분류한다."""
    if value is None:
        return "NULL"
    text = str(value)
    if "/" in text:
        return "INTERVAL"
    if text.startswith("FY"):
        return "FY"
    return {4: "YYYY", 7: "YYYY-MM", 10: "YYYY-MM-DD"}.get(
        len(text), "OTHER_SCHEMA_VALID")


def load_annotation_bank(path: str | Path, *,
                         source_by_id: Mapping[str, Mapping[str, object]],
                         ) -> dict[str, dict]:
    """원본 bank의 schema/provenance/source span만 검증한다.

    의미 verdict를 다시 추론하지 않으며, ``gold_article_sha256``은 producer hash
    정의가 저장소에 없으므로 기록값의 형식만 확인한다.
    """
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("r06 extraction annotation bank must be a JSON array")
    rows: dict[str, dict] = {}
    required = {
        "schema_version", "usage", "article_id", "content_sha256",
        "gold_article_sha256", "gold_version", "gold_guideline_version",
        "guideline_version", "review", "coverage", "gold_issues",
        "mention_reviews", "role_reviews",
    }
    for index, row in enumerate(payload):
        where = f"annotation_bank[{index}]"
        if not isinstance(row, dict) or set(row) != required:
            raise ValueError(f"{where}: fields differ")
        article_id = row["article_id"]
        if not isinstance(article_id, str) or not article_id or article_id in rows:
            raise ValueError(f"{where}: duplicate/invalid article_id")
        if (row["schema_version"] != ANNOTATION_BANK_SCHEMA_VERSION
                or row["usage"] != ANNOTATION_BANK_USAGE
                or row["gold_version"] != "articlelocal-semantic-gold-v1.4"
                or row["gold_guideline_version"] != "articlelocal-semantic-guideline-r06.0"
                or row["guideline_version"] != ANNOTATION_BANK_GUIDELINE_VERSION):
            raise ValueError(f"{where}: sidecar/gold/guideline contract differs")
        source = source_by_id.get(article_id)
        if source is None:
            raise ValueError(f"{where}: processed source row missing")
        content = source["article"]
        digest = sha256(str(content).encode("utf-8")).hexdigest()
        if row["content_sha256"] != digest:
            raise ValueError(f"{where}: source content SHA differs")
        if not isinstance(row["gold_article_sha256"], str) or not _SHA256.fullmatch(
                row["gold_article_sha256"]):
            raise ValueError(f"{where}: recorded Gold article SHA is malformed")
        if (not isinstance(row["mention_reviews"], list)
                or not isinstance(row["role_reviews"], list)
                or not isinstance(row["gold_issues"], list)
                or not isinstance(row["review"], dict)
                or not isinstance(row["coverage"], dict)):
            raise ValueError(f"{where}: review collections/metadata malformed")
        for review in row["mention_reviews"]:
            _validate_review_span(review, str(content), where=where)
        for role_review in row["role_reviews"]:
            if not isinstance(role_review, dict) or not isinstance(
                    role_review.get("candidates"), list):
                raise ValueError(f"{where}: malformed role review")
            for candidate in role_review["candidates"]:
                _validate_review_span(candidate, str(content), where=where)
        rows[article_id] = row
    return rows


def _validate_review_span(review: object, content: str, *, where: str) -> None:
    if not isinstance(review, dict) or not isinstance(review.get("span"), dict):
        raise ValueError(f"{where}: review span object required")
    span = review["span"]
    start, end, text = span.get("start"), span.get("end"), span.get("text")
    if (not isinstance(start, int) or isinstance(start, bool)
            or not isinstance(end, int) or isinstance(end, bool)
            or not isinstance(text, str) or not 0 <= start < end <= len(content)
            or content[start:end] != text):
        raise ValueError(f"{where}: review span does not round-trip")


def _authority_candidate(*, candidate_id: str, kind: str, owner_id: str,
                         role: str | None, role_status: str | None,
                         review: Mapping[str, object], proposed_label: str) -> dict:
    return {
        "candidate_id": candidate_id,
        "kind": kind,
        "owner_id": owner_id,
        "role": role,
        "role_status": role_status,
        "span": dict(review["span"]),
        "proposed_label": proposed_label,
        "verdict": review["verdict"],
        "reason": review["reason_code"],
        "responsibility": ("ROLE_FILLER_EXISTENCE"
                           if kind == "PARTICIPANT" else "MENTION_EXISTENCE"),
        "related_gold_ids": list(review.get("related_gold_ids", [])),
    }


def project_annotation_bank(*, selected_ids: Sequence[str],
                            gold_by_id: Mapping[str, Mapping[str, object]],
                            source_by_id: Mapping[str, Mapping[str, object]],
                            bank_by_id: Mapping[str, Mapping[str, object]],
                            source_sidecar_path: str | Path,
                            ) -> tuple[ReviewedNegativeAuthority, dict, dict]:
    """선택 train fixture의 bank verdict를 compact authority로 투영한다."""
    if len(set(selected_ids)) != len(tuple(selected_ids)):
        raise ValueError("engineering authority selection has duplicate article IDs")
    article_payloads: list[dict] = []
    provenance_rows: list[dict] = []
    source_reviews: list[dict] = []
    conflict_count = 0

    for article_id in selected_ids:
        gold = gold_by_id.get(article_id)
        bank = bank_by_id.get(article_id)
        source = source_by_id.get(article_id)
        if gold is None or bank is None or source is None:
            raise ValueError(f"{article_id}: Gold/source/sidecar join is incomplete")
        content = str(source["article"])
        candidates: list[dict] = []
        entity_gold = {
            (row["span"]["start"], row["span"]["end"]): row
            for row in gold["entity_mentions"]
        }
        time_gold = {
            (row["span"]["start"], row["span"]["end"]): row
            for row in gold["time_mentions"]
        }
        entity_protected = set(entity_gold)
        event_by_id = {row["event_id"]: row for row in gold["events"]}
        role_collection = {"ACTOR": "actors", "TARGET": "targets", "PLACE": "places"}
        for event in gold["events"]:
            for collection in role_collection.values():
                entity_protected.update(
                    (value["span"]["start"], value["span"]["end"])
                    for value in event[collection])
        entity_protected.update(
            (row["assertor"]["span"]["start"], row["assertor"]["span"]["end"])
            for row in gold["statements"] if row["assertor"] is not None)

        for review in bank["mention_reviews"]:
            kind = review["kind"]
            if kind not in ("ENTITY", "TIME"):
                raise ValueError(f"{article_id}:{review.get('review_id')}: unknown mention kind")
            coordinate = (review["span"]["start"], review["span"]["end"])
            verdict = review["verdict"]
            if kind == "ENTITY":
                if verdict == "NEGATIVE" and coordinate in entity_protected:
                    conflict_count += 1
                    raise ValueError(f"{article_id}:{review['review_id']}: protected Entity negative")
                if verdict == "POSITIVE":
                    exact = entity_gold.get(coordinate)
                    if exact is None:
                        conflict_count += 1
                        raise ValueError(f"{article_id}:{review['review_id']}: Entity positive misses Gold")
                    proposed_label = exact["type"]
                else:
                    proposed_label = "ENTITY"
            else:
                if verdict == "NEGATIVE" and coordinate in time_gold:
                    conflict_count += 1
                    raise ValueError(f"{article_id}:{review['review_id']}: protected Time negative")
                if verdict == "POSITIVE" and coordinate not in time_gold:
                    conflict_count += 1
                    raise ValueError(f"{article_id}:{review['review_id']}: Time positive misses Gold")
                proposed_label = "TIME"
            candidate_id = f"M:{review['review_id']}"
            candidates.append(_authority_candidate(
                candidate_id=candidate_id, kind=kind, owner_id=article_id,
                role=None, role_status=None, review=review,
                proposed_label=proposed_label))
            provenance_rows.append(_provenance_row(
                article_id, candidate_id, review, bank, source_sidecar_path,
                owner_id=article_id, role=None, role_status=None))

        for role_review in bank["role_reviews"]:
            event_id = role_review["event_id"]
            role = role_review["role"]
            status = role_review["status"]
            event = event_by_id.get(event_id)
            if event is None or role not in role_collection:
                raise ValueError(f"{article_id}: role review owner/role is unknown")
            gold_fillers = event[role_collection[role]]
            for review in role_review["candidates"]:
                coordinate = (review["span"]["start"], review["span"]["end"])
                verdict = review["verdict"]
                if verdict == "NEGATIVE" and (
                        status != "ABSENT"
                        or review["reason_code"] != "REVIEWED_ROLE_ABSENT"
                        or gold_fillers):
                    conflict_count += 1
                    raise ValueError(
                        f"{article_id}:{review['review_id']}: participant negative lacks ABSENT authority")
                if verdict == "POSITIVE" and not any(
                        (row["span"]["start"], row["span"]["end"]) == coordinate
                        for row in gold_fillers):
                    conflict_count += 1
                    raise ValueError(f"{article_id}:{review['review_id']}: participant positive misses Gold")
                candidate_id = f"R:{event_id}:{role}:{review['review_id']}"
                candidates.append(_authority_candidate(
                    candidate_id=candidate_id, kind="PARTICIPANT", owner_id=event_id,
                    role=role, role_status=status, review=review,
                    proposed_label=role))
                provenance_rows.append(_provenance_row(
                    article_id, candidate_id, review, bank, source_sidecar_path,
                    owner_id=event_id, role=role, role_status=status))

        candidate_ids = [row["candidate_id"] for row in candidates]
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError(f"{article_id}: projected candidate ID collision")
        article_payloads.append({
            "article_id": article_id,
            "content_sha256": gold["content_sha256"],
            "candidates": candidates,
        })
        source_reviews.append({
            "article_id": article_id,
            "source_review_status": bank["review"].get("status"),
            "source_verifier": bank["review"].get("verifier"),
        })

    authority_payload = {
        "schema_version": AUTHORITY_SCHEMA_VERSION,
        "split": "train",
        "authority_id": "r06-preflight-6-engineering-authority-v1",
        "reviewer": ENGINEERING_AUTHORITY_STATUS,
        "review_version": PROJECTION_POLICY_VERSION,
        "articles": article_payloads,
    }
    authority = ReviewedNegativeAuthority.from_payload(authority_payload)
    provenance = {
        "schema_version": "r06-preflight-negative-authority-provenance-v1",
        "status": ENGINEERING_AUTHORITY_STATUS,
        "source_usage": ANNOTATION_BANK_USAGE,
        "source_sidecar": Path(source_sidecar_path).name,
        "source_sidecar_sha256": file_sha256(source_sidecar_path),
        "source_reviews": source_reviews,
        "main_training_allowed": False,
        "purpose": ENGINEERING_PURPOSE,
        "projection_policy_version": PROJECTION_POLICY_VERSION,
        "authority_canonical_sha256": authority.sha256,
        "gold_article_sha256_contract": "RECORDED_ONLY_PRODUCER_HASH_DEFINITION_NOT_FOUND",
        "rows": provenance_rows,
    }
    audit = {
        "gold_protection_violations": conflict_count,
        "projected_article_count": len(article_payloads),
        "projected_candidate_count": sum(len(row["candidates"]) for row in article_payloads),
    }
    return authority, authority_payload, provenance | {"projection_audit": audit}


def _provenance_row(article_id: str, candidate_id: str,
                    review: Mapping[str, object], bank: Mapping[str, object],
                    source_sidecar_path: str | Path, *, owner_id: str,
                    role: str | None, role_status: str | None) -> dict:
    return {
        "article_id": article_id,
        "authority_candidate_id": candidate_id,
        "owner_id": owner_id,
        "role": role,
        "role_status": role_status,
        "original_review_id": review["review_id"],
        "verdict": review["verdict"],
        "reason_code": review["reason_code"],
        "reason_detail": review.get("reason_detail"),
        "stratum": review.get("stratum"),
        "origin": review.get("origin"),
        "related_gold_ids": list(review.get("related_gold_ids", [])),
        "source_sidecar_sha256": file_sha256(source_sidecar_path),
        "source_article_review_status": bank["review"].get("status"),
        "source_verifier": bank["review"].get("verifier"),
    }


def article_target_census(article: ValidatedGoldArticle,
                          target: ArticleTargets) -> dict:
    """한 compiler 결과의 구조·pair universe·review authority support를 센다."""
    gold = article.annotations
    reviewed = Counter((row.kind, row.verdict) for row in target.reviewed_span_decisions)
    pair_counts = {name: universe.counts() for name, universe in target.pairs.items()}
    expected_event_coref = sum(
        len(cluster["event_ids"]) * (len(cluster["event_ids"]) - 1) // 2
        for cluster in gold["event_clusters"])
    if pair_counts["event_coreference"]["positive"] != expected_event_coref:
        raise ValueError(f"{article.raw.article_id}: EventCluster membership/coref mismatch")
    return {
        "article_id": article.raw.article_id,
        "split": article.split,
        "validation_contract_id": article.validation_contract_id,
        "counts": {
            "events": len(gold["events"]),
            "statements": len(gold["statements"]),
            "entity_mentions": len(gold["entity_mentions"]),
            "entity_clusters": len(gold["entity_clusters"]),
            "time_mentions": len(gold["time_mentions"]),
            "event_clusters": len(gold["event_clusters"]),
        },
        "pair_universes": pair_counts,
        "positive_support": {
            "event_time": pair_counts["event_time"]["positive"],
            "assertor_entity": pair_counts["assertor_entity"]["positive"],
            "about": pair_counts["about"]["positive"],
            "causes": pair_counts["causes"]["positive"],
            "primary_supervised_pair": target.primary.counts()["positive"],
        },
        "reviewed_authority": {
            "entity_negative": reviewed[("ENTITY", "NEGATIVE")],
            "time_negative": reviewed[("TIME", "NEGATIVE")],
            "participant_negative": reviewed[("PARTICIPANT", "NEGATIVE")],
            "ignore": sum(count for (kind, verdict), count in reviewed.items()
                          if verdict == "IGNORE"),
            "omission_suspected": sum(count for (kind, verdict), count in reviewed.items()
                                      if verdict == "OMISSION_SUSPECTED"),
        },
        "time_normalization": {
            "supervise": sum(row.normalization_mask == "SUPERVISE"
                             for row in target.time_normalization),
            "ignore": sum(row.normalization_mask == "IGNORE"
                          for row in target.time_normalization),
            "forms": dict(Counter(
                normalized_time_form(row["normalized_value"])
                for row in gold["time_mentions"])),
        },
        "event_coreference_membership_check": {
            "expected_positive": expected_event_coref,
            "actual_positive": pair_counts["event_coreference"]["positive"],
            "eligible_negative": pair_counts["event_coreference"]["negative"],
            "multi_member_cluster_count": sum(len(row["event_ids"]) > 1
                                              for row in gold["event_clusters"]),
            "max_event_span_chars": max(
                (row["span"]["end"] - row["span"]["start"]
                 for row in gold["events"]), default=0),
        },
    }


def aggregate_census(rows: Sequence[Mapping[str, object]]) -> dict:
    totals = Counter()
    time_forms = Counter()
    pair_totals: dict[str, Counter] = {}
    for row in rows:
        totals.update(row["counts"])
        totals.update(row["positive_support"])
        totals.update(row["reviewed_authority"])
        time_forms.update(row["time_normalization"]["forms"])
        for task, counts in row["pair_universes"].items():
            pair_totals.setdefault(task, Counter()).update(counts)
    critical = {
        "event_coreference_positive": pair_totals.get("event_coreference", Counter())["positive"],
        "entity_coreference_positive": pair_totals.get("entity_coreference", Counter())["positive"],
        "event_time_positive": totals["event_time"],
        "assertor_entity_positive": totals["assertor_entity"],
        "about_positive": totals["about"],
        "causes_positive": totals["causes"],
        "primary_supervised_pair": totals["primary_supervised_pair"],
        "reviewed_entity_negative": totals["entity_negative"],
        "reviewed_time_negative": totals["time_negative"],
        "reviewed_participant_negative": totals["participant_negative"],
    }
    return {
        "article_count": len(rows),
        "counts": dict(sorted(totals.items())),
        "time_normalization_forms": dict(sorted(time_forms.items())),
        "pair_universes": {task: dict(counter) for task, counter in sorted(pair_totals.items())},
        "critical_support": critical,
        "all_critical_support_nonzero": all(value > 0 for value in critical.values()),
    }
