"""Frozen scorer의 accepted span을 occurrence family와 canonical mention으로 닫는다.

이 decoder는 추가 학습 없는 provisional boundary 정책이다. 같은 원문 위치의
predicate/clause와 의미 범위를 함께 확인하며 overlap chain은 family로 합치지 않는다.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from hashlib import sha256
import json
import math
from pathlib import Path
import re
import time
from typing import Any, Mapping

from .resolved_contracts import AcceptedSpanHypothesis, CanonicalMention
from .semantic_v3 import stable_prediction_id


_PREDICATE = re.compile(
    r"[가-힣]+(?:하였다|되었다|시켰다|했다|한다|였다|었다|았다|됐다|된다|하며|면서|다고|라고|해|할|고)"
)
_ACTOR = re.compile(r"([A-Za-z0-9가-힣]{1,24})(?:은|는|이|가)(?=\s|$)")
_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")
_TIME = re.compile(r"어제|오늘|내일|그제|모레|지난해|내년|올해|작년|\d{1,4}년|\d{1,2}월|\d{1,2}일")
_PUNCTUATION = re.compile(r"[\s.,;:!?()\[\]{}\"'“”‘’「」『』]*\Z")
_SUBJECT_PREFIX = re.compile(
    r"[\s.,;:!?()\[\]{}\"'“”‘’]*[A-Za-z0-9가-힣]+(?:은|는|이|가)[\s.,;:!?()\[\]{}\"'“”‘’]*\Z"
)
_CLAUSE_DELIMITER = re.compile(r"[,;:!?]|[가-힣]+(?:해|하며|면서)(?=\s)")
_QUOTE_PAIRS = {"“": "”", "‘": "’", "「": "」", "『": "』", '"': '"', "'": "'"}


@dataclass(frozen=True, slots=True)
class MentionPolicy:
    family_policy_id: str
    cross_kind_policy_id: str
    margin_clip: float
    tie_kind_order: tuple[str, ...]
    ambiguous_margin: float

    @classmethod
    def load(cls, path: Path | None = None) -> "MentionPolicy":
        path = path or Path(__file__).resolve().parents[1] / "configs/semantic-mention-v22.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        if (value.get("schema_version") != "articlelocal-semantic-mention-policy-v22-v1"
            or value.get("unresolved_boundary_behavior") != "KEEP_SEPARATE_AND_COUNT"
            or value.get("learned_scores") != "FROZEN_HEADS_ONLY"):
            raise ValueError("unsupported semantic mention policy")
        policy = cls(
            str(value["family_policy_id"]), str(value["cross_kind_policy_id"]),
            float(value["margin_clip"]), tuple(value["tie_kind_order"]),
            float(value["ambiguous_margin"]),
        )
        if (policy.family_policy_id != "V22_SEMANTIC_FAMILY_CONSOLIDATION_V1"
            or policy.cross_kind_policy_id != "V22_EXACT_CROSS_KIND_ARBITRATION_V1"
            or policy.tie_kind_order != ("EVENT", "STATEMENT")
            or not 0.0 < policy.margin_clip < 0.5
            or policy.ambiguous_margin < 0.0):
            raise ValueError("semantic mention policy contract differs")
        return policy


@dataclass(frozen=True, slots=True)
class _Signature:
    anchor: tuple[int, int] | None
    predicate_count: int
    actor: str | None
    modality: tuple[bool, bool, bool]
    numbers: tuple[str, ...]
    times: tuple[str, ...]
    quoted: bool
    clause_scope: tuple[int, int]
    quote_scope: tuple[int, int] | None


def _source_scopes(prepared, sentence_index: int,
                   anchor_position: int) -> tuple[tuple[int, int], tuple[int, int] | None]:
    sentence = next((row for row in prepared.sentences
                     if int(row["sentence_index"]) == sentence_index), None)
    if sentence is None:
        start, end = 0, len(prepared.article.content)
    else:
        start, end = int(sentence["start"]), int(sentence["end"])
    body = prepared.article.content[start:end]
    boundaries = [start]
    boundaries.extend(start + match.end() for match in _CLAUSE_DELIMITER.finditer(body))
    boundaries.append(end)
    clause = next(
        ((left, right) for left, right in zip(boundaries, boundaries[1:])
         if left <= anchor_position < right),
        (start, end),
    )
    quote_ranges = []
    stack: list[tuple[str, int]] = []
    for local_index, char in enumerate(body):
        if stack and char == _QUOTE_PAIRS[stack[-1][0]]:
            _opening, open_index = stack.pop()
            quote_ranges.append((start + open_index, start + local_index + 1))
        elif char in _QUOTE_PAIRS:
            stack.append((char, local_index))
    quote = next((span for span in sorted(quote_ranges, key=lambda item: item[1] - item[0])
                  if span[0] <= anchor_position < span[1]), None)
    return clause, quote


def _signature(hypothesis: AcceptedSpanHypothesis, prepared,
               triggers: tuple[Mapping[str, Any], ...]) -> _Signature:
    source = prepared.article.content
    start, end = hypothesis.grounding.char_start, hypothesis.grounding.char_end
    text = source[start:end]
    lexical = tuple((start + match.start(), start + match.end())
                    for match in _PREDICATE.finditer(text))
    contained = tuple(
        (int(row["char_start"]), int(row["char_end"]))
        for row in triggers
        if int(row["sentence_index"]) == hypothesis.sentence_index
        and start <= int(row["char_start"]) and int(row["char_end"]) <= end
    )
    # 한 span에 별개 predicate가 둘 이상 있으면 단일 occurrence의 boundary 대안이 아니다.
    anchor = (lexical[0] if len(lexical) == 1 else
              contained[0] if not lexical and len(contained) == 1 else None)
    if len(contained) > 1 or (len(lexical) == 1 and contained
                              and not any(max(a[0], lexical[0][0]) < min(a[1], lexical[0][1])
                                          for a in contained)):
        anchor = None
    actor_match = _ACTOR.search(text)
    actor = actor_match.group(1) if actor_match else None
    modality = (
        bool(re.search(r"않|못|아니|부정", text)),
        bool(re.search(r"가능|가정|예정|전망|수\s+있|할\s+것", text)),
        bool(re.search(r"밝혔|말했|발언|인용|보도|전했", text)),
    )
    clause_scope, quote_scope = _source_scopes(
        prepared, hypothesis.sentence_index,
        anchor[0] if anchor else start,
    )
    return _Signature(
        anchor, len(lexical), actor, modality,
        tuple(_NUMBER.findall(text)), tuple(_TIME.findall(text)),
        bool(re.search(r"[\"'“”‘’「」『』]", text)),
        clause_scope, quote_scope,
    )


def _compatible(left: AcceptedSpanHypothesis, right: AcceptedSpanHypothesis,
                left_signature: _Signature, right_signature: _Signature,
                source: str) -> bool:
    if (left.kind != right.kind
        or left.grounding.article_version_id != right.grounding.article_version_id
        or left.sentence_index != right.sentence_index):
        return False
    ls, le = left.grounding.char_start, left.grounding.char_end
    rs, re_ = right.grounding.char_start, right.grounding.char_end
    if (ls, le) == (rs, re_):
        return True
    if (left_signature.anchor is None or left_signature.anchor != right_signature.anchor
        or left_signature.predicate_count > 1 or right_signature.predicate_count > 1
        or left_signature.modality != right_signature.modality
        or left_signature.clause_scope != right_signature.clause_scope
        or left_signature.quote_scope != right_signature.quote_scope
        or left_signature.numbers != right_signature.numbers
        or left_signature.times != right_signature.times):
        return False
    if (left_signature.actor is not None and right_signature.actor is not None
        and left_signature.actor != right_signature.actor):
        return False
    if max(ls, rs) >= min(le, re_):
        return False
    prefix = source[min(ls, rs):max(ls, rs)]
    suffix = source[min(le, re_):max(le, re_)]
    # Shared predicate만으로는 부족하다. 차이는 표면 구두점/조사 또는 생략된 주어여야 한다.
    return bool((_PUNCTUATION.fullmatch(prefix) or _SUBJECT_PREFIX.fullmatch(prefix))
                and _PUNCTUATION.fullmatch(suffix))


def _representative_key(row: AcceptedSpanHypothesis):
    return (-row.boundary_score, -row.semantic_score,
            row.grounding.char_start, row.grounding.char_end, row.hypothesis_id)


def _margin(row: AcceptedSpanHypothesis, clip: float) -> float:
    def logit(value: float) -> float:
        clipped = min(1.0 - clip, max(clip, value))
        return math.log(clipped / (1.0 - clipped))

    return logit(row.semantic_score) - logit(row.semantic_threshold)


def _record(sink, kind: str, value: Mapping[str, Any]) -> None:
    if sink is not None and sink.level.value != "SUMMARY":
        sink.record(kind, value)


@dataclass(frozen=True, slots=True)
class BoundaryFamily:
    """같은 occurrence의 pairwise-compatible accepted hypothesis stage carrier."""

    family_id: str
    kind: str
    representative: AcceptedSpanHypothesis
    members: tuple[AcceptedSpanHypothesis, ...]

    def __post_init__(self) -> None:
        if (not self.family_id or not self.members
            or self.representative not in self.members
            or any(member.kind != self.kind for member in self.members)):
            raise ValueError("invalid semantic boundary family")


@dataclass(frozen=True, slots=True)
class ConsolidatedSemanticRun:
    propositions: tuple[Mapping[str, Any], ...]
    mentions: tuple[CanonicalMention, ...]
    trace: Mapping[str, Any]
    debug: Mapping[str, Any]


def consolidate(prepared, hypotheses: tuple[AcceptedSpanHypothesis, ...],
                triggers: tuple[Mapping[str, Any], ...], *, policy: MentionPolicy,
                semantic_config: Mapping[str, Any], proposer_checkpoint_sha: str,
                v3_checkpoint_sha: str, diagnostic_sink=None) -> ConsolidatedSemanticRun:
    """pairwise family→대표→exact same-proposition kind 결정을 순서대로 수행한다."""

    started = time.perf_counter()
    source = prepared.article.content
    for row in hypotheses:
        row.grounding.text(
            article_version_id=prepared.article.article_version_id,
            source_text=source,
        )
    signatures = {row.hypothesis_id: _signature(row, prepared, triggers) for row in hypotheses}
    families: list[list[AcceptedSpanHypothesis]] = []
    counts: Counter[str] = Counter()
    counts["ACCEPTED_HYPOTHESIS"] = len(hypotheses)
    for row in sorted(hypotheses, key=_representative_key):
        signature = signatures[row.hypothesis_id]
        eligible = [
            family for family in families
            if all(_compatible(row, member, signature,
                               signatures[member.hypothesis_id], source)
                   for member in family)
        ]
        if len(eligible) == 1:
            eligible[0].append(row)
            counts["ABSORBED_BOUNDARY"] += 1
        else:
            families.append([row])
            if signature.anchor is None or len(eligible) > 1:
                counts["unresolved_boundary_family"] += 1
                _record(diagnostic_sink, "decision", {
                    "decision": "UNRESOLVED_BOUNDARY_FAMILY",
                    "family_policy_id": policy.family_policy_id,
                    "hypothesis_id": row.hypothesis_id,
                    "article_version_id": row.grounding.article_version_id,
                    "char_start": row.grounding.char_start,
                    "char_end": row.grounding.char_end,
                    "reason": "AMBIGUOUS_PREDICATE" if signature.anchor is None else "MULTIPLE_PAIRWISE_FAMILIES",
                })
    boundary_families = []
    for family in families:
        representative = min(family, key=_representative_key)
        family_id = "SMF-" + sha256(
            f"{representative.grounding.article_version_id}|{representative.kind}|"
            f"{representative.hypothesis_id}".encode("utf-8")
        ).hexdigest()[:20]
        boundary_families.append(BoundaryFamily(
            family_id, representative.kind, representative, tuple(family),
        ))
    representatives = [family.representative for family in boundary_families]
    counts["BOUNDARY_FAMILY"] = len(families)
    family_sizes = {family.representative.hypothesis_id: len(family.members)
                    for family in boundary_families}
    for family in boundary_families:
        representative = family.representative
        for member in family.members:
            if member.hypothesis_id != representative.hypothesis_id:
                _record(diagnostic_sink, "decision", {
                    "decision": "ABSORBED_BOUNDARY",
                    "family_policy_id": policy.family_policy_id,
                    "family_id": family.family_id,
                    "hypothesis_id": member.hypothesis_id,
                    "representative_hypothesis_id": representative.hypothesis_id,
                    "article_version_id": member.grounding.article_version_id,
                    "char_start": member.grounding.char_start,
                    "char_end": member.grounding.char_end,
                })
        _record(diagnostic_sink, "decision", {
            "decision": "FAMILY_REPRESENTATIVE",
            "family_policy_id": policy.family_policy_id,
            "family_id": family.family_id,
            "representative_hypothesis_id": representative.hypothesis_id,
            "family_size": len(family.members),
            "article_version_id": representative.grounding.article_version_id,
            "char_start": representative.grounding.char_start,
            "char_end": representative.grounding.char_end,
        })
    # 동일 kind·동일 좌표의 별도 family가 생겨도 최종 inventory는 한 mention만 둔다.
    by_same_kind: dict[tuple[str, int, int, int], AcceptedSpanHypothesis] = {}
    for row in representatives:
        key = (row.kind, row.sentence_index, row.grounding.char_start, row.grounding.char_end)
        prior = by_same_kind.get(key)
        if prior is None or _representative_key(row) < _representative_key(prior):
            if prior is not None:
                counts["EXACT_SAME_KIND_COLLISION"] += 1
                _record(diagnostic_sink, "decision", {
                    "decision": "EXACT_SAME_KIND_COLLISION",
                    "winner_hypothesis_id": row.hypothesis_id,
                    "absorbed_hypothesis_id": prior.hypothesis_id,
                    "article_version_id": row.grounding.article_version_id,
                    "char_start": row.grounding.char_start,
                    "char_end": row.grounding.char_end,
                })
            by_same_kind[key] = row
        else:
            counts["EXACT_SAME_KIND_COLLISION"] += 1
            _record(diagnostic_sink, "decision", {
                "decision": "EXACT_SAME_KIND_COLLISION",
                "winner_hypothesis_id": prior.hypothesis_id,
                "absorbed_hypothesis_id": row.hypothesis_id,
                "article_version_id": row.grounding.article_version_id,
                "char_start": row.grounding.char_start,
                "char_end": row.grounding.char_end,
            })
    by_span: dict[tuple[str, int, int, int], list[AcceptedSpanHypothesis]] = defaultdict(list)
    for row in by_same_kind.values():
        by_span[(row.grounding.article_version_id, row.sentence_index,
                 row.grounding.char_start, row.grounding.char_end)].append(row)
    kept: list[AcceptedSpanHypothesis] = []
    for rows in by_span.values():
        if len(rows) != 2 or {row.kind for row in rows} != {"EVENT", "STATEMENT"}:
            kept.extend(rows)
            continue
        event = next(row for row in rows if row.kind == "EVENT")
        statement = next(row for row in rows if row.kind == "STATEMENT")
        left, right = signatures[event.hypothesis_id], signatures[statement.hypothesis_id]
        if (left.predicate_count > 1 or right.predicate_count > 1
            or (left.modality[2] and left.quoted)
            or left.modality != right.modality):
            kept.extend(rows)
            counts["DISTINCT_EXACT_SPAN_PROPOSITION"] += 1
            continue
        event_margin = _margin(event, policy.margin_clip)
        statement_margin = _margin(statement, policy.margin_clip)
        winner = min(
            rows,
            key=lambda row: (-_margin(row, policy.margin_clip),
                             policy.tie_kind_order.index(row.kind)),
        )
        loser = statement if winner is event else event
        kept.append(winner)
        counts["EXACT_CROSS_KIND_ARBITRATED"] += 1
        ambiguity = abs(event_margin - statement_margin) <= policy.ambiguous_margin
        if ambiguity:
            counts["ambiguous_cross_kind_margin"] += 1
        _record(diagnostic_sink, "decision", {
            "decision": "EXACT_CROSS_KIND_ARBITRATED",
            "policy_id": policy.cross_kind_policy_id,
            "winner_hypothesis_id": winner.hypothesis_id,
            "absorbed_hypothesis_id": loser.hypothesis_id,
            "article_version_id": winner.grounding.article_version_id,
            "char_start": winner.grounding.char_start,
            "char_end": winner.grounding.char_end,
            "event_margin": event_margin,
            "statement_margin": statement_margin,
            "margin_meaning": "FROZEN_THRESHOLD_RELATIVE_DECODER_SCORE_NOT_PROBABILITY",
            "ambiguous": ambiguity,
        })
    # arbitration 후 동일 proposition의 cross-kind exact collision이 남지 않아야 한다.
    active = {(row.kind, row.sentence_index, row.grounding.char_start,
               row.grounding.char_end) for row in kept}
    for row in kept:
        other = "STATEMENT" if row.kind == "EVENT" else "EVENT"
        if (other, row.sentence_index, row.grounding.char_start,
            row.grounding.char_end) in active:
            signature = signatures[row.hypothesis_id]
            if signature.predicate_count <= 1 and not signature.modality[2]:
                raise RuntimeError("same canonical proposition survived exact cross-kind arbitration")
    kept.sort(key=lambda row: (row.sentence_index, row.grounding.char_start,
                               row.grounding.char_end, row.kind))
    ranks: Counter[int] = Counter()
    propositions = []
    mentions = []
    for row in kept:
        ranks[row.sentence_index] += 1
        prediction_id = stable_prediction_id(
            prepared.article, semantic_config["canonical_runtime_config_id"],
            row.kind, row.grounding.char_start, row.grounding.char_end,
        )
        mentions.append(CanonicalMention(
            prediction_id, row.kind, row.grounding, row.semantic_score,
            family_sizes[row.hypothesis_id],
        ))
        propositions.append({
            "prediction_id": prediction_id,
            "proposal_id": row.hypothesis_id,
            "kind": row.kind,
            "article_id": prepared.article.article_id,
            "sentence_id": row.sentence_id,
            "sentence_index": row.sentence_index,
            "char_start": row.grounding.char_start,
            "char_end": row.grounding.char_end,
            "token_start": row.token_start,
            "token_end": row.token_end,
            "text": prepared.grounding_text(
                row.grounding.char_start, row.grounding.char_end, row.sentence_index,
            ),
            "semantic_score": row.semantic_score,
            "boundary_score": row.boundary_score,
            "semantic_threshold": row.semantic_threshold,
            "boundary_threshold": row.boundary_threshold,
            "semantic_pass": True,
            "boundary_pass": True,
            "verifier_score": row.semantic_score,
            "acceptance_score": row.semantic_score,
            "decoder_rank": ranks[row.sentence_index],
            "checkpoint_sha": v3_checkpoint_sha,
            "proposer_checkpoint_sha": proposer_checkpoint_sha,
            "runtime_config_id": semantic_config["canonical_runtime_config_id"],
            "provenance": {
                "source": "EXPERIMENTAL_PREDICTION",
                "semantic_runtime_source_config_id": semantic_config["source_semantic_runtime_config_id"],
                "decoder_decision": policy.family_policy_id,
            },
            "representation_source": (
                "frozen KF-DeBERTa RAW L8 + same-seed canonical-A DCE; "
                "Canonical V3 candidate-only scoring"
            ),
        })
    counts["CANONICAL_MENTION"] = len(kept)
    counts["TRANSFERRED_CANONICAL"] = len(kept)
    counts["DISCARDED_HYPOTHESIS"] = len(hypotheses) - len(kept)
    trace = {
        "stage": "③ Semantic Canonical Mention Closure",
        "component": "pairwise boundary family + exact cross-kind arbitration",
        "input_count": len(hypotheses),
        "candidate_count": len(hypotheses),
        "output_count": len(kept),
        "drop_reason_counts": {
            key: counts[key] for key in (
                "ABSORBED_BOUNDARY", "EXACT_SAME_KIND_COLLISION",
                "EXACT_CROSS_KIND_ARBITRATED",
            )
        },
        "transition_counts": dict(counts),
        "warnings": ["Provisional semantic boundary policy; validate on fixed Stage12 inputs."],
        "elapsed_seconds": time.perf_counter() - started,
        "family_policy_id": policy.family_policy_id,
        "cross_kind_policy_id": policy.cross_kind_policy_id,
    }
    return ConsolidatedSemanticRun(tuple(propositions), tuple(mentions), trace, {})
