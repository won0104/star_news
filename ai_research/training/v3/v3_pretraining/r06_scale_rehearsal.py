"""r06 Gold100 scale rehearsal의 train-only sidecar projection 계약.

원 annotation bank의 verdict를 바꾸지 않는다. Gold issue는 사용자가 승인한
structured code/owner/span 교집합이 같은 의미 책임의 reviewed NEGATIVE와 직접
충돌할 때에만 row 단위로 quarantine한다. 명시적인 Gold와의 모순은 quarantine로
숨기지 않고 fail-closed한다.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Mapping, Sequence

from training.v3_pretraining.negative_authority import (
    SCHEMA_VERSION as AUTHORITY_SCHEMA_VERSION,
    VERDICTS,
    ReviewedNegativeAuthority,
)
from training.v3_pretraining.r06_intake import (
    ANNOTATION_BANK_USAGE,
    _authority_candidate,
    canonical_sha256,
    file_sha256,
)


TRAIN73_AUTHORITY_STATUS = "PROVISIONAL_ENGINEERING_TRAIN73_ONLY"
TRAIN73_PURPOSE = "R06_GOLD100_FRESH73_SCALE_REHEARSAL"
TRAIN73_PROJECTION_POLICY_VERSION = "r06-train73-gold-issue-row-quarantine-v1"
QUARANTINE_DISPOSITION = "QUARANTINED_GOLD_ISSUE_DIRECT_CONFLICT"
KNOWN_QUARANTINE_ISSUE_CODES = frozenset({
    "TIME_MENTION_MISSING", "REQUIRED_ENTITY_MISSING", "ROLE_REVIEW_REQUIRED",
})


def spans_overlap(left: Mapping[str, object], right: Mapping[str, object]) -> bool:
    """Return the approved end-exclusive source-overlap predicate."""
    return max(int(left["start"]), int(right["start"])) < min(
        int(left["end"]), int(right["end"]))


def _validate_issue(issue: object, content: str, *, article_id: str) -> Mapping[str, object]:
    if not isinstance(issue, Mapping) or set(issue) != {
            "issue_id", "code", "related_gold_ids", "evidence_spans", "detail"}:
        raise ValueError(f"{article_id}: malformed Gold issue")
    if (not isinstance(issue["issue_id"], str) or not issue["issue_id"]
            or not isinstance(issue["code"], str) or not issue["code"]
            or not isinstance(issue["related_gold_ids"], list)
            or any(not isinstance(value, str) or not value
                   for value in issue["related_gold_ids"])
            or not isinstance(issue["evidence_spans"], list)):
        raise ValueError(f"{article_id}: malformed Gold issue identity/reference")
    for span in issue["evidence_spans"]:
        if (not isinstance(span, Mapping) or set(span) != {"start", "end", "text"}
                or not isinstance(span["start"], int)
                or isinstance(span["start"], bool)
                or not isinstance(span["end"], int)
                or isinstance(span["end"], bool)
                or not isinstance(span["text"], str)
                or not 0 <= span["start"] < span["end"] <= len(content)
                or content[span["start"]:span["end"]] != span["text"]):
            raise ValueError(f"{article_id}:{issue['issue_id']}: issue evidence span drift")
    return issue


def _matched_issues(*, review: Mapping[str, object], kind: str,
                    owner_id: str, issues: Sequence[Mapping[str, object]]) -> tuple[str, ...]:
    """Match only the explicitly approved structured direct-conflict rules."""
    if review["verdict"] != "NEGATIVE":
        return ()
    if kind == "TIME":
        codes = {"TIME_MENTION_MISSING"}
    elif kind == "ENTITY":
        codes = {"REQUIRED_ENTITY_MISSING"}
    elif kind == "PARTICIPANT":
        codes = {"ROLE_REVIEW_REQUIRED", "REQUIRED_ENTITY_MISSING"}
    else:
        raise ValueError(f"unknown reviewed kind: {kind}")
    matched = []
    for issue in issues:
        if issue["code"] not in codes:
            continue
        if kind == "PARTICIPANT" and owner_id not in issue["related_gold_ids"]:
            continue
        if any(spans_overlap(review["span"], evidence)
               for evidence in issue["evidence_spans"]):
            matched.append(str(issue["issue_id"]))
    return tuple(sorted(set(matched)))


def _disposition(verdict: str, quarantined: bool) -> str:
    if quarantined:
        return QUARANTINE_DISPOSITION
    return {
        "NEGATIVE": "USED_NEGATIVE",
        "POSITIVE": "USED_POSITIVE_CONFIRMATION",
        "IGNORE": "IGNORED_BY_SIDECAR",
        "OMISSION_SUSPECTED": "OMISSION_SUSPECTED",
    }[verdict]


def _provenance_row(*, article_id: str, candidate_id: str,
                    review: Mapping[str, object], bank: Mapping[str, object],
                    owner_id: str, role: str | None, role_status: str | None,
                    matched_issue_ids: Sequence[str]) -> dict[str, object]:
    return {
        "article_id": article_id,
        "authority_candidate_id": candidate_id,
        "original_review_id": review["review_id"],
        "kind": ("PARTICIPANT" if role is not None else review["kind"]),
        "owner_id": owner_id,
        "role": role,
        "role_status": role_status,
        "source_verdict": review["verdict"],
        "source_reason_code": review["reason_code"],
        "source_reason_detail": review.get("reason_detail"),
        "source_span": dict(review["span"]),
        "stratum": review.get("stratum"),
        "origin": review.get("origin"),
        "related_gold_ids": list(review.get("related_gold_ids", [])),
        "disposition": _disposition(review["verdict"], bool(matched_issue_ids)),
        "matched_gold_issue_ids": list(matched_issue_ids),
        "quarantine_reason": (
            "STRUCTURED_CODE_OWNER_SPAN_DIRECT_CONFLICT"
            if matched_issue_ids else None),
        "source_article_review_status": bank["review"].get("status"),
        "source_verifier": bank["review"].get("verifier"),
    }


def project_train73_annotation_bank(
        *, selected_ids: Sequence[str],
        gold_by_id: Mapping[str, Mapping[str, object]],
        source_by_id: Mapping[str, Mapping[str, object]],
        bank_by_id: Mapping[str, Mapping[str, object]],
        source_sidecar_path: str | Path,
        expected_article_count: int = 73,
        authority_id: str = "r06-train73-engineering-authority-v1",
        reviewer_status: str = TRAIN73_AUTHORITY_STATUS,
        purpose: str = TRAIN73_PURPOSE,
        main_training_allowed: bool = False,
) -> tuple[ReviewedNegativeAuthority, dict[str, object], dict[str, object]]:
    """Project train reviews, excluding only direct-conflict negative rows.

    The defaults preserve the historical train73 engineering artifact. A new
    cohort supplies its own identity and explicit training approval.
    """
    selected = tuple(selected_ids)
    if (len(selected) != expected_article_count or len(set(selected)) != len(selected)
            or expected_article_count < 1 or not authority_id or not reviewer_status):
        raise ValueError("train annotation projection requires fixed unique article IDs")
    article_payloads = []
    provenance_rows = []
    source_reviews = []
    issue_codes = Counter()
    dispositions = Counter()
    quarantine_by_kind = Counter()
    unknown_issue_codes = Counter()

    for article_id in selected:
        gold = gold_by_id.get(article_id)
        bank = bank_by_id.get(article_id)
        source = source_by_id.get(article_id)
        if gold is None or bank is None or source is None:
            raise ValueError(f"{article_id}: Gold/source/sidecar join is incomplete")
        content = str(source["article"])
        if bank["content_sha256"] != gold["content_sha256"]:
            raise ValueError(f"{article_id}: sidecar/Gold content SHA differs")
        issues = tuple(_validate_issue(row, content, article_id=article_id)
                       for row in bank["gold_issues"])
        issue_codes.update(str(row["code"]) for row in issues)
        unknown_issue_codes.update(str(row["code"]) for row in issues
                                   if row["code"] not in KNOWN_QUARANTINE_ISSUE_CODES)

        entity_gold = {(row["span"]["start"], row["span"]["end"]): row
                       for row in gold["entity_mentions"]}
        time_gold = {(row["span"]["start"], row["span"]["end"]): row
                     for row in gold["time_mentions"]}
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

        candidates = []
        candidate_id_counts: Counter[str] = Counter()

        def allocate_candidate_id(base_id: str) -> str:
            candidate_id_counts[base_id] += 1
            ordinal = candidate_id_counts[base_id]
            return base_id if ordinal == 1 else f"{base_id}:SOURCE_ROW_{ordinal}"

        for review in bank["mention_reviews"]:
            kind = review.get("kind")
            verdict = review.get("verdict")
            if kind not in ("ENTITY", "TIME") or verdict not in VERDICTS:
                raise ValueError(f"{article_id}:{review.get('review_id')}: unknown kind/verdict")
            coordinate = (review["span"]["start"], review["span"]["end"])
            if kind == "ENTITY":
                if verdict == "NEGATIVE" and coordinate in entity_protected:
                    raise ValueError(f"{article_id}:{review['review_id']}: protected Entity negative")
                if verdict == "POSITIVE":
                    exact = entity_gold.get(coordinate)
                    if exact is None or review.get("reason_code") != "CONFIRMED_GOLD":
                        raise ValueError(f"{article_id}:{review['review_id']}: Entity positive misses Gold")
                    proposed_label = exact["type"]
                else:
                    proposed_label = "ENTITY"
            else:
                if verdict == "NEGATIVE" and coordinate in time_gold:
                    raise ValueError(f"{article_id}:{review['review_id']}: protected Time negative")
                if verdict == "POSITIVE" and (
                        coordinate not in time_gold
                        or review.get("reason_code") != "CONFIRMED_GOLD"):
                    raise ValueError(f"{article_id}:{review['review_id']}: Time positive misses Gold")
                proposed_label = "TIME"
            candidate_id = allocate_candidate_id(f"M:{review['review_id']}")
            matched = _matched_issues(
                review=review, kind=kind, owner_id=article_id, issues=issues)
            provenance = _provenance_row(
                article_id=article_id, candidate_id=candidate_id, review=review,
                bank=bank, owner_id=article_id, role=None, role_status=None,
                matched_issue_ids=matched)
            provenance_rows.append(provenance)
            dispositions[(kind, provenance["disposition"])] += 1
            if matched:
                quarantine_by_kind[kind] += 1
                continue
            candidates.append(_authority_candidate(
                candidate_id=candidate_id, kind=kind, owner_id=article_id,
                role=None, role_status=None, review=review,
                proposed_label=proposed_label))

        for role_review in bank["role_reviews"]:
            event_id = role_review.get("event_id")
            role = role_review.get("role")
            status = role_review.get("status")
            event = event_by_id.get(event_id)
            if event is None or role not in role_collection:
                raise ValueError(f"{article_id}: role review owner/role is unknown")
            gold_fillers = event[role_collection[role]]
            for review in role_review["candidates"]:
                if review.get("verdict") not in VERDICTS:
                    raise ValueError(f"{article_id}:{review.get('review_id')}: unknown verdict")
                coordinate = (review["span"]["start"], review["span"]["end"])
                verdict = review["verdict"]
                # ABSENT authority contradicts any listed filler for this exact Event/role.
                if verdict == "NEGATIVE" and (
                        status != "ABSENT"
                        or review.get("reason_code") != "REVIEWED_ROLE_ABSENT"
                        or gold_fillers):
                    raise ValueError(
                        f"{article_id}:{review['review_id']}: participant negative contradicts Gold/ABSENT")
                if verdict == "POSITIVE" and (
                        review.get("reason_code") != "CONFIRMED_GOLD"
                        or not any((row["span"]["start"], row["span"]["end"]) == coordinate
                                   for row in gold_fillers)):
                    raise ValueError(
                        f"{article_id}:{review['review_id']}: participant positive misses Gold")
                candidate_id = allocate_candidate_id(
                    f"R:{event_id}:{role}:{review['review_id']}")
                matched = _matched_issues(
                    review=review, kind="PARTICIPANT", owner_id=str(event_id),
                    issues=issues)
                provenance = _provenance_row(
                    article_id=article_id, candidate_id=candidate_id, review=review,
                    bank=bank, owner_id=str(event_id), role=str(role),
                    role_status=str(status), matched_issue_ids=matched)
                provenance_rows.append(provenance)
                dispositions[("PARTICIPANT", provenance["disposition"])] += 1
                if matched:
                    quarantine_by_kind["PARTICIPANT"] += 1
                    continue
                candidates.append(_authority_candidate(
                    candidate_id=candidate_id, kind="PARTICIPANT",
                    owner_id=str(event_id), role=str(role), role_status=str(status),
                    review=review, proposed_label=str(role)))

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
            "coverage": dict(bank["coverage"]),
            "gold_issue_count": len(issues),
        })

    authority_payload = {
        "schema_version": AUTHORITY_SCHEMA_VERSION,
        "split": "train",
        "authority_id": authority_id,
        "reviewer": reviewer_status,
        "review_version": TRAIN73_PROJECTION_POLICY_VERSION,
        "articles": article_payloads,
    }
    authority = ReviewedNegativeAuthority.from_payload(authority_payload)
    provenance = {
        "schema_version": "r06-train73-negative-authority-provenance-v1",
        "status": reviewer_status,
        "source_usage": ANNOTATION_BANK_USAGE,
        "source_sidecar": Path(source_sidecar_path).name,
        "source_sidecar_sha256": file_sha256(source_sidecar_path),
        "source_reviews": source_reviews,
        "main_training_allowed": main_training_allowed,
        "purpose": purpose,
        "projection_policy_version": TRAIN73_PROJECTION_POLICY_VERSION,
        "authority_canonical_sha256": authority.sha256,
        "authority_payload_sha256": canonical_sha256(authority_payload),
        "gold_issue_code_counts": dict(sorted(issue_codes.items())),
        "unknown_issue_code_counts": dict(sorted(unknown_issue_codes.items())),
        "disposition_counts": {
            f"{kind}:{disposition}": count
            for (kind, disposition), count in sorted(dispositions.items())},
        "quarantine_counts_by_kind": dict(sorted(quarantine_by_kind.items())),
        "gold_protection_violations": 0,
        "rows": provenance_rows,
    }
    return authority, authority_payload, provenance
