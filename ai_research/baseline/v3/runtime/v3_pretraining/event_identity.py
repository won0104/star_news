"""같은 실제 occurrence만 article-local Event identity로 닫는 scalar 경계.

평가하지 않은 pair는 음성이 아니다. complete-link 또는 명시적 strict equivalence
witness만 병합 근거다. 모든 member의 role/Time/trigger 사실을 유지한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from itertools import combinations
from typing import Mapping, Sequence

from runtime.v3_pretraining.source_layout import RawArticle


ROLES = ("ACTOR", "TARGET", "PLACE")


@dataclass(frozen=True, slots=True)
class MemberRoleFact:
    evidence_id: str
    role: str
    start: int
    end: int
    text: str
    entity_id: str | None
    endpoint_status: str


@dataclass(frozen=True, slots=True)
class EventMember:
    member_id: str
    start: int
    end: int
    text: str
    trigger_start: int
    trigger_end: int
    trigger_text: str
    roles: tuple[MemberRoleFact, ...]
    time_ids: tuple[str, ...]
    aligned: bool = True


@dataclass(frozen=True, slots=True)
class LocalRoleFact:
    role: str
    entity_id: str | None
    start: int
    end: int
    text: str
    endpoint_status: str
    evidence_ids: tuple[str, ...]
    member_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class LocalTimeFact:
    time_id: str
    member_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class LocalEventState:
    """최종 semantic carrier: scalar source facts만 포함하고 tensor/member feature는 없다."""

    local_id: str
    member_ids: tuple[str, ...]
    representative_member_id: str
    start: int
    end: int
    text: str
    triggers: tuple[tuple[int, int, str, str], ...]  # start, end, text, member ID
    roles: tuple[LocalRoleFact, ...]
    times: tuple[LocalTimeFact, ...]
    conflict_flags: tuple[str, ...]
    status: str


@dataclass(frozen=True, slots=True)
class EventClosure:
    article_version_id: str
    content_sha256: str
    events: tuple[LocalEventState, ...]
    member_to_cluster: Mapping[str, str]
    unassessed_pairs: int
    unaligned_members: int
    b3_witness_pairs: int
    status: str
    source_mode: str


def _pair_key(a: str, b: str) -> tuple[str, str]:
    return (a, b) if a < b else (b, a)


def close_event_identity(article: RawArticle, members: Sequence[EventMember], *,
                         pair_decisions: Mapping[tuple[str, str], bool],
                         strict_equivalence_pairs: frozenset[tuple[str, str]] = frozenset(),
                         source_mode: str = "PREDICTED") -> EventClosure:
    """동일성 결정 후 최종 ID와 모든 member fact를 만들며 미평가를 partial로 남긴다."""
    if source_mode not in ("PREDICTED", "GOLD_ORACLE"):
        raise ValueError("unknown Event membership provenance")
    ids = [row.member_id for row in members]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate Event member ID")
    by_id = {row.member_id: row for row in members}
    for row in members:
        if not 0 <= row.start < row.end <= len(article.content) or article.content[row.start:row.end] != row.text:
            raise ValueError("Event member lost exact semantic span")
        if not 0 <= row.trigger_start < row.trigger_end <= len(article.content) or article.content[row.trigger_start:row.trigger_end] != row.trigger_text:
            raise ValueError("Event member lost exact trigger")
        if len(set(row.time_ids)) != len(row.time_ids):
            raise ValueError("duplicate member Time attachment")
        for role in row.roles:
            if (role.role not in ROLES or not role.evidence_id or
                    not 0 <= role.start < role.end <= len(article.content) or
                    article.content[role.start:role.end] != role.text):
                raise ValueError("Event role lost exact source grounding")
            if role.role in ("ACTOR", "TARGET") and role.endpoint_status == "SPAN_ONLY" and source_mode == "GOLD_ORACLE":
                raise ValueError("Gold ACTOR/TARGET cannot be SPAN_ONLY")
    normalized: dict[tuple[str, str], bool] = {}
    for (a, b), decision in pair_decisions.items():
        if a not in by_id or b not in by_id or a == b:
            raise ValueError("Event identity decision references unknown/self member")
        key = _pair_key(a, b)
        if key in normalized and normalized[key] != bool(decision):
            raise ValueError("conflicting symmetric Event pair decisions")
        normalized[key] = bool(decision)
    witnesses = {_pair_key(a, b) for a, b in strict_equivalence_pairs}
    if any(a not in by_id or b not in by_id or a == b for a, b in witnesses):
        raise ValueError("strict equivalence witness references unknown/self Event")
    if any(key in normalized and not normalized[key] for key in witnesses):
        raise ValueError("B3 witness contradicts evaluated negative pair")
    decisions = {**normalized, **{key: True for key in witnesses}}
    unassessed = sum(_pair_key(a, b) not in decisions for a, b in combinations(ids, 2))
    groups: list[set[str]] = [{member_id} for member_id in sorted(ids)]
    for a, b in sorted(key for key, decision in decisions.items() if decision):
        if not (by_id[a].aligned and by_id[b].aligned):
            continue
        left = next(group for group in groups if a in group)
        right = next(group for group in groups if b in group)
        if left is right:
            continue
        if all(decisions.get(_pair_key(x, y), False) and by_id[x].aligned and by_id[y].aligned
               for x in left for y in right):
            left.update(right)
            groups.remove(right)
    events = []
    remap = {}
    for group in groups:
        ordered = sorted((by_id[mid] for mid in group), key=lambda row: (row.start, row.end, row.member_id))
        representative = ordered[0]
        member_ids = tuple(sorted(group))
        local_id = "EVCL:" + sha256(f"{article.article_version_id}:{article.content_sha256}:{','.join(member_ids)}".encode()).hexdigest()[:16]
        role_groups: dict[tuple[str, str | None, int, int, str, str], list[tuple[str, str]]] = {}
        time_groups: dict[str, set[str]] = {}
        for row in ordered:
            for role in row.roles:
                key = (role.role, role.entity_id, role.start, role.end, role.text, role.endpoint_status)
                role_groups.setdefault(key, []).append((row.member_id, role.evidence_id))
            for time_id in row.time_ids:
                time_groups.setdefault(time_id, set()).add(row.member_id)
        roles = tuple(LocalRoleFact(key[0], key[1], key[2], key[3], key[4], key[5],
                                    tuple(sorted(eid for _, eid in sources)),
                                    tuple(sorted({mid for mid, _ in sources})))
                      for key, sources in sorted(role_groups.items(), key=lambda item: str(item[0])))
        times = tuple(LocalTimeFact(tid, tuple(sorted(member_ids)))
                      for tid, member_ids in sorted(time_groups.items()))
        endpoints_by_grounding: dict[tuple[str, int, int], set[str]] = {}
        for role in roles:
            if role.entity_id is not None:
                endpoints_by_grounding.setdefault((role.role, role.start, role.end), set()).add(role.entity_id)
        conflict = ("ROLE_ENDPOINT_CONFLICT",) if any(len(values) > 1 for values in endpoints_by_grounding.values()) else ()
        status = "PARTIAL_ALIGNMENT" if any(not row.aligned for row in ordered) else "CONFLICT" if conflict else "READY"
        event = LocalEventState(local_id, member_ids, representative.member_id,
                                representative.start, representative.end, representative.text,
                                tuple((row.trigger_start, row.trigger_end, row.trigger_text, row.member_id)
                                      for row in ordered), roles, times, conflict, status)
        events.append(event)
        remap.update({mid: local_id for mid in member_ids})
    events.sort(key=lambda row: (row.start, row.end, row.local_id))
    status = ("BOUNDED_PARTIAL" if unassessed else
              "PARTIAL_ALIGNMENT" if any(not row.aligned for row in members) else
              "CONFLICT" if any(row.conflict_flags for row in events) else "READY")
    return EventClosure(article.article_version_id, article.content_sha256,
                        tuple(events), remap, unassessed,
                        sum(not row.aligned for row in members), len(witnesses),
                        status, source_mode)
