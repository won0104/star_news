"""Gold-free v3 request orchestrator and strict diagnostic checkpoint startup.

The worker owns one frozen producer and one v3 core. Each request owns its source
layout and transient tensor leases; only scalar PUBLIC output crosses the boundary.
Selection budgets and pair logit cutoffs are engineering diagnostics, not calibrated
service policy. No database writer or Gold reader is called by this module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from threading import BoundedSemaphore
from time import perf_counter
from typing import Any, Mapping

import torch

from models.v3_pretraining.architecture import V3Core
from models.v3_pretraining.frozen_features import FrozenBackboneFeatureBuilder
from runtime.v3_pretraining.attribution_scoring import (asserted_by_facts, bridge_token_states,
                                                        decode_assertor_source,
                                                        score_final_relations)
from runtime.v3_pretraining.canonical_text import GroundedStatement, SourceGrounding
from runtime.v3_pretraining.entity_scoring import score_and_close_entity
from runtime.v3_pretraining.entity_union import (ENTITY_TYPES, EntityCandidateBudget, build_entity_candidates,
                                                evidence_from_assertor_decode,
                                                evidence_from_entity_decode,
                                                evidence_from_role_decode)
from runtime.v3_pretraining.event_features import (EventFeatureProvenance,
                                                  build_event_member_features,
                                                  finalize_cluster_features)
from runtime.v3_pretraining.event_identity import EventMember, MemberRoleFact
from runtime.v3_pretraining.event_scoring import (EventIdentityDecodeConfig,
                                                 score_event_identity)
from runtime.v3_pretraining.extraction_decode import (DecodeBudget, DecodedSourceSpan,
                                                      decode_source_spans, event_source_state,
                                                      source_decode_context)
from runtime.v3_pretraining.primary_scoring import score_final_primary
from runtime.v3_pretraining.public_graph import V3ConstructionResult, project_public
from runtime.v3_pretraining.source_batch import source_windows_from_layout
from runtime.v3_pretraining.source_layout import LayoutBuilder, RawArticle
from runtime.v3_pretraining.temporal import (TimeMentionEvidence, close_time_occurrences,
                                             infer_source_time)
from runtime.v3_pretraining.temporal_scoring import (EventTimeDecodeConfig,
                                                    encode_event_time_features,
                                                    score_event_time)
from runtime.v3_pretraining.tokenizer import load_pinned_fast_tokenizer


@dataclass(frozen=True, slots=True)
class ServingBudget:
    """Bound request work before calibrated extraction and selection exist."""

    source: DecodeBudget = field(default_factory=lambda: DecodeBudget(24, 24, 64, 32))
    participant: DecodeBudget = field(default_factory=lambda: DecodeBudget(12, 12, 24, 16))
    max_events: int = 64
    max_statements: int = 64
    max_entities: int = 64
    max_times: int = 64
    max_triggers: int = 64
    max_entity_candidates: int = 128
    pair_chunk_size: int = 64
    max_event_time_pairs: int = 4096
    max_event_coreference_pairs: int = 4096
    max_relation_pairs: int = 4096

    def __post_init__(self) -> None:
        if min(self.max_events, self.max_statements, self.max_entities,
               self.max_times, self.max_triggers, self.max_entity_candidates,
               self.pair_chunk_size, self.max_event_time_pairs,
               self.max_event_coreference_pairs, self.max_relation_pairs) <= 0:
            raise ValueError("serving engineering budgets must be positive")


@dataclass(frozen=True, slots=True)
class ServingResult:
    public: dict[str, Any]
    audit: dict[str, Any]


def _bounded(spans: tuple[DecodedSourceSpan, ...], limit: int) -> tuple[DecodedSourceSpan, ...]:
    selected = sorted(spans, key=lambda row: (-row.score, row.start, row.end, row.label or ""))[:limit]
    return tuple(sorted(selected, key=lambda row: (row.start, row.end, row.label or "")))


def _span_id(prefix: str, span: DecodedSourceSpan) -> str:
    return f"{prefix}:{span.start}:{span.end}:{span.label or ''}"


def _storage_census(*tensors: torch.Tensor | None) -> dict[str, int]:
    """Count unique backing storage in one live owner without exporting pointers."""
    live = [row for row in tensors if row is not None]
    storage = {row.untyped_storage().data_ptr(): row.untyped_storage().nbytes()
               for row in live if row.numel()}
    return {"tensor_views": len(live), "unique_storage_count": len(storage),
            "unique_storage_bytes": sum(storage.values())}


class V3ServingWorker:
    """One eval worker; a semaphore keeps request leases from overlapping on shared modules."""

    def __init__(self, core: V3Core, backbone: torch.nn.Module, tokenizer: Any,
                 tokenizer_sha256: str, *, budget: ServingBudget = ServingBudget(),
                 producer_version: str = "V3_FRESH_SMOKE_DIAGNOSTIC") -> None:
        core.require_full_model()
        if tokenizer_sha256 != core.config.tokenizer_sha256 or any(
                parameter.requires_grad for parameter in backbone.parameters()):
            raise ValueError("serving requires pinned tokenizer and frozen backbone")
        self.core = core.eval()
        self.backbone = backbone.eval()
        self.layout_builder = LayoutBuilder(tokenizer, tokenizer_sha256=tokenizer_sha256)
        self.pad_token_id = tokenizer.pad_token_id
        self.budget = budget
        self.producer_version = producer_version
        self._request_slot = BoundedSemaphore(1)

    @torch.no_grad()
    def analyze(self, *, article_id: str, content: str, title: str = "",
                article_version_id: str | None = None,
                published_at: str | None = None,
                enable_primary: bool = True) -> ServingResult:
        """Run one predicted request, then return only scalar PUBLIC graph and audit."""
        digest = sha256(content.encode("utf-8")).hexdigest()
        raw = RawArticle(article_id, article_version_id or f"{article_id}:{digest[:16]}",
                         content, digest, published_at)
        with self._request_slot:
            return self._analyze_owned(raw, title=title, enable_primary=enable_primary)

    def _analyze_owned(self, raw: RawArticle, *, title: str,
                       enable_primary: bool) -> ServingResult:
        start_clock = perf_counter()
        counts = {"backbone": 0, "dce": 0}
        handles = [self.backbone.register_forward_hook(
            lambda *_: counts.__setitem__("backbone", counts["backbone"] + 1)),
            self.core.document_context.register_forward_hook(
                lambda *_: counts.__setitem__("dce", counts["dce"] + 1))]
        shared = time_lease = member_lease = final = source_context = None
        stages: dict[str, int] = {}
        source_pairs: dict[str, dict[str, int]] = {}
        partial: list[str] = []
        storage: dict[str, dict[str, int]] = {}
        try:
            layout = self.layout_builder.build(raw)
            batch = source_windows_from_layout(layout, pad_token_id=self.pad_token_id).article_view(raw, view="all")
            backbone_output = FrozenBackboneFeatureBuilder(self.backbone).build(batch)
            if set(backbone_output.hidden_by_layer) != {8, 10, 12}:
                raise ValueError("serving backbone captured nonselective layer set")
            capture = getattr(self.backbone, "required_layer_capture", None)
            if capture is not None and (capture.capture_hook_count != 3 or
                                        capture.current_context_tensor_count != 0):
                raise RuntimeError("pinned selective capture hooks or cleanup regressed")
            shared = self.core.forward_shared(batch, backbone_output)
            after_shared = perf_counter()
            storage["backbone_shared"] = _storage_census(
                *(backbone_output.layer(layer) for layer in (8, 10, 12)),
                shared.token_states, shared.sentence_states,
                shared.document_state, shared.proposal_logits)
            shared_source = id(shared.token_states)
            source_context = source_decode_context(layout, shared, self.core)
            for kind, limit in (("EVENT", self.budget.max_events),
                                ("STATEMENT", self.budget.max_statements),
                                ("ENTITY", self.budget.max_entities),
                                ("TIME", self.budget.max_times),
                                ("TRIGGER", self.budget.max_triggers)):
                decoded = decode_source_spans(kind=kind, layout=layout, batch=batch,
                                              backbone=backbone_output, shared=shared,
                                              core=self.core, budget=self.budget.source,
                                              context=source_context)
                stages[kind] = shared_source
                source_pairs[kind] = {"eligible": decoded.eligible_pairs,
                                      "scored": decoded.scored_pairs,
                                      "retained": min(len(decoded.spans), limit)}
                if decoded.partial or len(decoded.spans) > limit:
                    partial.append(kind)
                if kind == "EVENT":
                    event_spans = _bounded(decoded.spans, limit)
                elif kind == "STATEMENT":
                    statement_spans = _bounded(decoded.spans, limit)
                elif kind == "ENTITY":
                    entity_spans = _bounded(decoded.spans, limit)
                elif kind == "TIME":
                    time_spans = _bounded(decoded.spans, limit)
                else:
                    trigger_spans = _bounded(decoded.spans, limit)
            source_context.release_generic_endpoints()

            # A member without a predicted trigger is omitted with an explicit partial audit.
            events: dict[str, tuple[DecodedSourceSpan, DecodedSourceSpan]] = {}
            for span in event_spans:
                options = [row for row in trigger_spans
                           if span.start <= row.start < row.end <= span.end]
                if not options:
                    partial.append("EVENT_TRIGGER_MISSING")
                    continue
                trigger = min(options, key=lambda row: (-row.score, row.start, row.end))
                events[_span_id("EM", span)] = (span, trigger)
            statements = {_span_id("ST", span): span for span in statement_spans}

            statement_states: dict[str, torch.Tensor] = {}
            if statements:
                aligned = [layout.align({"start": span.start, "end": span.end, "text": span.text})
                           for span in statements.values()]
                features = self.core.exact_source_span(
                    layout=layout, batch=batch, backbone=backbone_output,
                    token_states=shared.token_states, sentence_states=shared.sentence_states,
                    document_state=shared.document_state, candidate_encoder=self.core.candidate_span,
                    rows=[(row, "STATEMENT") for row in aligned])
                statement_states = {sid: features.states[index]
                                    for index, sid in enumerate(statements)}
                features = None
                stages["STATEMENT_FEATURE"] = shared_source

            assertors: dict[str, DecodedSourceSpan] = {}
            assertor_bridge_states = (bridge_token_states(
                layout, shared, bridge_positions=source_context.bridge_positions)
                if statements else None)
            for sid, span in statements.items():
                outcome = decode_assertor_source(
                    statement_id=sid, statement_alignment=layout.align(
                        {"start": span.start, "end": span.end, "text": span.text}),
                    layout=layout, batch=batch, backbone=backbone_output, shared=shared,
                    core=self.core, statement_state=statement_states[sid],
                    bridge_states=assertor_bridge_states)
                if outcome.span is not None:
                    assertors[sid] = outcome.span
                if outcome.partial:
                    partial.append("ASSERTOR")
            assertor_bridge_states = None
            stages["ASSERTOR"] = shared_source
            assertor_states: dict[str, torch.Tensor] = {}
            if assertors:
                aligned = [layout.align({"start": span.start, "end": span.end, "text": span.text})
                           for span in assertors.values()]
                features = self.core.exact_source_span(
                    layout=layout, batch=batch, backbone=backbone_output,
                    token_states=shared.token_states, sentence_states=shared.sentence_states,
                    document_state=shared.document_state, candidate_encoder=self.core.candidate_span,
                    rows=[(row, "STATEMENT") for row in aligned])
                assertor_states = {sid: features.states[index]
                                   for index, sid in enumerate(assertors)}
                features = None
            storage["statement_assertor"] = _storage_census(
                *statement_states.values(), *assertor_states.values())

            role_evidence = []
            participant_pairs = {"eligible": 0, "scored": 0}
            ner_coordinates = {(span.start, span.end) for span in entity_spans}
            for member_id, (event_span, _trigger) in events.items():
                alignment = layout.align({"start": event_span.start, "end": event_span.end,
                                          "text": event_span.text})
                event_state = event_source_state(
                    alignment=alignment, layout=layout, batch=batch,
                    backbone=backbone_output, shared=shared, core=self.core)
                for role in ("ACTOR", "TARGET", "PLACE"):
                    outcome = decode_source_spans(
                        kind="PARTICIPANT", layout=layout, batch=batch,
                        backbone=backbone_output, shared=shared, core=self.core,
                        budget=self.budget.participant, event_alignment=alignment, role=role,
                        context=source_context, event_state=event_state)
                    stages["PARTICIPANT"] = shared_source
                    participant_pairs["eligible"] += outcome.eligible_pairs
                    participant_pairs["scored"] += outcome.scored_pairs
                    if outcome.partial:
                        partial.append("PARTICIPANT")
                    if not outcome.spans:
                        continue
                    span = _bounded(outcome.spans, 1)[0]
                    referential = ("SPAN_ONLY" if role == "PLACE" and
                                   (span.start, span.end) not in ner_coordinates else "PROPOSED")
                    role_evidence.append(evidence_from_role_decode(
                        member_id, span, referential_state=referential))
                event_state = None
            source_context.close()
            after_extraction = perf_counter()

            evidence = list(evidence_from_entity_decode(entity_spans)) + role_evidence + [
                evidence_from_assertor_decode(sid, span) for sid, span in assertors.items()]
            universe = build_entity_candidates(raw, evidence,
                                               budget=EntityCandidateBudget(self.budget.max_entity_candidates))
            accepted = frozenset(row.evidence_id for row in role_evidence
                                 if row.role in ("ACTOR", "TARGET") or
                                 row.role == "PLACE" and row.referential_state != "SPAN_ONLY")
            entity_result = score_and_close_entity(
                universe=universe, layout=layout, batch=batch, backbone=backbone_output,
                shared=shared, core=self.core, accepted_role_evidence=accepted,
                statement_states=statement_states,
                pair_chunk_size=self.budget.pair_chunk_size,
                max_candidates=self.budget.max_entity_candidates)
            entity_closure = entity_result.closure
            if any(row.entity_type not in ENTITY_TYPES for row in entity_closure.entities):
                raise ValueError("predicted LocalEntity lacks one canonical five-type value")
            stages["ENTITY_RESOLUTION"] = shared_source
            after_entity = perf_counter()

            time_mentions = []
            for span in time_spans:
                value, _reason = infer_source_time(span.text, raw.published_at)
                time_mentions.append(TimeMentionEvidence(
                    _span_id("TM", span), span.start, span.end, span.text, value,
                    "SOURCE_RULE" if value is not None else "UNRESOLVED"))
            extra_rows = []
            for mid, (_event, trigger) in events.items():
                extra_rows.append(("TRIGGER:" + mid, layout.align(
                    {"start": trigger.start, "end": trigger.end, "text": trigger.text}), "TRIGGER"))
            for role in entity_closure.endpoints:
                if role.role != "ASSERTOR" and role.owner_id in events:
                    extra_rows.append(("ROLE:" + role.evidence_id, layout.align(
                        {"start": role.start, "end": role.end, "text": role.text}), "PARTICIPANT"))
            for entity in entity_closure.entities:
                extra_rows.append(("ENTITY:" + entity.local_id, layout.align(
                    {"start": entity.start, "end": entity.end, "text": entity.text}), "ENTITY"))
            time_lease = encode_event_time_features(
                layout=layout, batch=batch, backbone=backbone_output, shared=shared, core=self.core,
                events=[(mid, layout.align({"start": span.start, "end": span.end, "text": span.text}))
                        for mid, (span, _trigger) in events.items()],
                times=[(row.time_id, layout.align({"start": row.start, "end": row.end,
                                                   "text": row.text})) for row in time_mentions],
                extra_rows=extra_rows, source_mode="PREDICTED")
            storage["event_time"] = _storage_census(
                time_lease.event_states, time_lease.time_states, time_lease.document_state,
                *(time_lease.extra_states or {}).values(),
                *(time_lease.extra_residuals or {}).values(),
                *(time_lease.extra_link_logits or {}).values())
            stages["EVENT_TIME_FEATURE"] = shared_source
            shared.close()
            if not shared.closed or time_lease.closed or time_lease.event_states is None:
                raise RuntimeError("source feature handoff released Event/Time before attachment")
            backbone_output = None
            batch = None
            # Source-valid normalization is the only emitted value. The untrained format/character
            # head is executed for diagnosis, but cannot invent precision or overwrite the source.
            normalization_checked = 0
            if time_mentions:
                states = time_lease.time_states
                for index, row in enumerate(time_mentions):
                    if row.normalized_value is None:
                        continue
                    fmt, chars = self.core.task_modules["time_normalization"](
                        states[index:index + 1], length=len(row.normalized_value))
                    if not torch.isfinite(fmt).all() or not torch.isfinite(chars).all():
                        raise ValueError("nonfinite Time normalization prediction")
                    normalization_checked += 1
                    fmt = chars = None
                states = None
            attachments = score_event_time(
                time_lease, core=self.core, content_length=len(raw.content),
                config=EventTimeDecodeConfig(max_pairs=self.budget.max_event_time_pairs,
                                             chunk_size=self.budget.pair_chunk_size))
            occurrences = close_time_occurrences(raw, time_mentions, attachments.attached_pairs)
            after_time = perf_counter()
            if attachments.partial:
                partial.append("EVENT_TIME")
            occurrence_by_evidence = {eid: row.local_id for row in occurrences
                                      for eid in row.evidence_ids}
            endpoints_by_owner: dict[str, list] = {}
            for endpoint in entity_closure.endpoints:
                if endpoint.role != "ASSERTOR":
                    endpoints_by_owner.setdefault(endpoint.owner_id, []).append(endpoint)
            members = []
            for mid, (span, trigger) in events.items():
                roles = tuple(MemberRoleFact(row.evidence_id, row.role, row.start, row.end,
                                             row.text, row.local_entity_id, row.status)
                              for row in endpoints_by_owner.get(mid, ()))
                time_ids = tuple(sorted({occurrence_by_evidence[tid] for eid, tid in attachments.attached_pairs
                                         if eid == mid}))
                members.append(EventMember(mid, span.start, span.end, span.text,
                                           trigger.start, trigger.end, trigger.text,
                                           roles, time_ids))
            member_lease = build_event_member_features(
                time_lease, members=members, occurrences=occurrences,
                head=self.core.task_modules["event_coreference"],
                provenance=EventFeatureProvenance("PREDICTED", "PREDICTED"))
            storage["event_member"] = _storage_census(
                member_lease.channel_sums, member_lease.channel_counts,
                member_lease.member_states, member_lease.document_state,
                *(member_lease.role_states or {}).values())
            time_lease.close()
            if not time_lease.closed or member_lease.closed or member_lease.member_states is None:
                raise RuntimeError("Event member feature handoff released before coreference")
            identity = score_event_identity(
                raw, member_lease, core=self.core,
                config=EventIdentityDecodeConfig(
                    max_pairs=self.budget.max_event_coreference_pairs,
                    chunk_size=self.budget.pair_chunk_size))
            if identity.partial:
                partial.append("EVENT_IDENTITY")
            final = finalize_cluster_features(member_lease, identity.closure)
            storage["final_cluster"] = _storage_census(
                final.channel_means, final.channel_counts, final.conflict_mask,
                final.mean_reference, final.document_state, final.member_states,
                final.member_cluster_indices, final.role_unique_means, final.role_unique_mask)
            member_lease.close()
            if not member_lease.closed or final.closed or final.pending_consumers != {"RELATION", "PRIMARY"}:
                raise RuntimeError("final cluster feature handoff lost relation/Primary consumer")
            after_identity = perf_counter()
            relation = score_final_relations(
                core=self.core, final=final, closure=identity.closure,
                statement_states=statement_states, max_pairs=self.budget.max_relation_pairs,
                chunk_size=self.budget.pair_chunk_size)
            final.release("RELATION")
            if final.closed or final.pending_consumers != {"PRIMARY"}:
                raise RuntimeError("final cluster feature released before Primary consumer")
            if relation.partial:
                partial.append("RELATION")
            after_relation = perf_counter()
            scores = (score_final_primary(core=self.core, final=final,
                                          closure=identity.closure,
                                          statement_states=statement_states,
                                          assertor_states=assertor_states)
                      if enable_primary else ())
            final.release("PRIMARY")
            if not final.closed:
                raise RuntimeError("final cluster feature survived last consumer")
            statement_states.clear()
            assertor_states.clear()
            after_primary = perf_counter()
            grounded = tuple(GroundedStatement(
                sid, span.label, SourceGrounding(sid, span.start, span.end, span.text),
                SourceGrounding("ASSERTOR:" + sid, assertors[sid].start,
                                assertors[sid].end, assertors[sid].text)
                if sid in assertors else None) for sid, span in statements.items())
            construction = V3ConstructionResult(
                raw, title, identity.closure, entity_closure, grounded, occurrences,
                asserted_by_facts(entity_closure), relation.facts, scores,
                self.producer_version)
            public = project_public(construction, diagnostic_unfiltered=True)
            after_public = perf_counter()
            if counts != {"backbone": 1, "dce": 1} or len(set(stages.values())) != 1:
                raise RuntimeError("serving duplicated frozen producer/DCE or source representation")
            audit = {"mode": "GOLD_FREE_PREDICTED_DIAGNOSTIC",
                     "policy_status": "PROVISIONAL_ENGINEERING_ONLY",
                     "partial_stages": sorted(set(partial)),
                     "backbone_calls": counts["backbone"], "dce_calls": counts["dce"],
                     "captured_layers": [8, 10, 12],
                     "capture_hook_count": capture.capture_hook_count if capture is not None else None,
                     "source_representation_reused": len(set(stages.values())) == 1,
                     "source_consumers": sorted(stages),
                     "source_candidate_pairs": source_pairs,
                     "participant_candidate_pairs": participant_pairs,
                     "entity_candidates": len(universe.candidates),
                     "entity_clusters": len(entity_closure.entities),
                     "all_entities_canonical_type": True,
                     "entity_candidates_dropped_ner": universe.dropped_ner,
                     "entity_candidates_dropped_role": universe.dropped_role,
                     "entity_coreference_pairs_scored": entity_result.scored_coreference_pairs,
                     "entity_role_pairs_scored": entity_result.scored_role_entity_pairs,
                     "event_time_pairs_eligible": attachments.eligible_pairs,
                     "event_time_pairs_scored": attachments.scored_pairs,
                     "event_coreference_pairs_eligible": identity.eligible_pairs,
                     "event_coreference_pairs_scored": identity.scored_pairs,
                     "about_pairs_eligible": relation.eligible_about,
                     "about_pairs_scored": relation.scored_about,
                     "causes_pairs_eligible": relation.eligible_causes,
                     "causes_pairs_scored": relation.scored_causes,
                     "storage_census": storage,
                     "event_members": len(events), "final_event_clusters": len(identity.closure.events),
                     "statements": len(statements), "time_mentions": len(time_mentions),
                     "time_normalization_checked": normalization_checked,
                     "unresolved_time_mentions": sum(row.normalized_value is None for row in time_mentions),
                     "noncalendar_time_occurrences": sum(not row.calendar_eligible for row in occurrences),
                     "time_semantics": [
                         {"local_id": row.local_id, "start": row.start, "end": row.end,
                          "text": row.text, "normalized_value": row.normalized_value,
                          "granularity": row.granularity,
                          "normalization_status": row.normalization_status,
                          "attachment_status": row.attachment_status,
                          "calendar_eligible": row.calendar_eligible}
                         for row in occurrences],
                     "span_only_place": sum(row.role == "PLACE" and row.status == "SPAN_ONLY"
                                            for row in entity_closure.endpoints),
                     "span_only_assertor": sum(row.role == "ASSERTOR" and row.status == "SPAN_ONLY"
                                               for row in entity_closure.endpoints),
                     "role_derived_entities": sum(any(eid.startswith("ROLE-PRED:")
                                                      for eid in row.evidence_ids)
                                                  for row in entity_closure.entities),
                     "assertor_derived_entities": sum(any(eid.startswith("ASSERTOR-PRED:")
                                                          for eid in row.evidence_ids)
                                                      for row in entity_closure.entities),
                     "entity_type_conflicts": [
                         {"local_id": row.local_id, "canonical_type": row.entity_type,
                          "observed_types": list(row.observed_types),
                          "member_type_evidence": [
                              {"candidate_id": cid, "predicted_type": kind,
                               "log_probabilities": list(values)}
                              for cid, kind, values in row.member_type_evidence]}
                         for row in entity_closure.entities if row.status == "TYPE_CONFLICT"],
                     "relation_scored_pairs": relation.scored_about + relation.scored_causes,
                     "stage_latency_ms": {
                         "source_backbone_shared": round((after_shared - start_clock) * 1000, 3),
                         "source_extraction": round((after_extraction - after_shared) * 1000, 3),
                         "entity_resolution": round((after_entity - after_extraction) * 1000, 3),
                         "time_attachment": round((after_time - after_entity) * 1000, 3),
                         "event_identity": round((after_identity - after_time) * 1000, 3),
                         "relations": round((after_relation - after_identity) * 1000, 3),
                         "primary": round((after_primary - after_relation) * 1000, 3),
                         "public_projection": round((after_public - after_primary) * 1000, 3)},
                     "elapsed_ms": round((perf_counter() - start_clock) * 1000, 3),
                     "all_tensor_leases_closed": all(
                         lease is None or lease.closed for lease in
                         (shared, time_lease, member_lease, final))}
            if not audit["all_tensor_leases_closed"]:
                raise RuntimeError("request tensor lease escaped last consumer")
            return ServingResult(public, audit)
        finally:
            if source_context is not None and not source_context.closed:
                source_context.close()
            for lease in (final, member_lease, time_lease, shared):
                if lease is not None and not lease.closed:
                    lease.close()
            for handle in handles:
                handle.remove()


def load_diagnostic_worker(checkpoint_path: str | Path, *,
                           budget: ServingBudget = ServingBudget()) -> V3ServingWorker:
    """Strictly load a stage-13 smoke core at startup without reading Gold articles.

    The returned worker remains diagnostic: smoke weights and Primary scores are
    never promoted to a trained or persistence-ready service model.
    """
    from models.v3_pretraining.task_contract import HEAD_TASKS
    from training.v3_pretraining.checkpoint import (FORMAT_VERSION, _json_digest,
                                                   label_mappings, producer_hashes)
    from training.v3_pretraining.harness import (HarnessConfig, fresh_full_core,
                                                 load_pinned_backbone, parameter_manifest)

    payload = torch.load(checkpoint_path, map_location="cpu", weights_only=True)
    required = {"format_version", "mode", "run_id", "seed", "harness_config",
                "harness_config_sha256", "architecture_config", "architecture_config_sha256",
                "backbone", "tokenizer", "task_registry", "label_mappings", "producer_hashes",
                "parameter_manifest", "parameter_ownership_audit", "source_snapshot",
                "model_state", "optimizer_state", "scheduler_state", "scaler_state",
                "rng_state", "sampler_state", "training_state", "eval_reference"}
    if not isinstance(payload, dict) or set(payload) != required or payload.get("format_version") != FORMAT_VERSION or payload.get("mode") != "ENGINEERING_SMOKE_ONLY":
        raise ValueError("incomplete or foreign diagnostic v3 checkpoint")
    config_data = payload["harness_config"]
    if (set(config_data) != set(HarnessConfig.__dataclass_fields__) or
            _json_digest(config_data) != payload["harness_config_sha256"] or
            payload["run_id"] != config_data["run_id"] or
            payload["seed"] != config_data["seed"]):
        raise ValueError("serving checkpoint run/config identity differs")
    config = HarnessConfig(**config_data)
    config.validate()
    core = fresh_full_core(config)
    if (payload["architecture_config_sha256"] != core.config.fingerprint() or
            _json_digest(payload["architecture_config"]) != core.config.fingerprint() or
            payload["task_registry"] != list(HEAD_TASKS) or
            payload["label_mappings"] != label_mappings() or
            payload["producer_hashes"] != producer_hashes() or
            payload["parameter_manifest"] != list(parameter_manifest(core)) or
            set(payload["model_state"]) != set(core.state_dict())):
        raise ValueError("serving checkpoint architecture/producer/parameter manifest differs")
    snapshot = payload["source_snapshot"]
    if (not isinstance(snapshot, dict) or
            set(snapshot) != {"source_join_sha256", "split_sha256", "exposure"} or
            any(not isinstance(snapshot[key], str) or len(snapshot[key]) != 64
                for key in ("source_join_sha256", "split_sha256")) or
            not isinstance(snapshot["exposure"], list) or not snapshot["exposure"] or
            any(not isinstance(row, dict) or
                set(row) != {"article_id", "gold_file", "gold_sha256", "source_sha256", "split"}
                or row["split"] != "train" or
                any(not isinstance(row[key], str) or len(row[key]) != 64
                    for key in ("gold_sha256", "source_sha256"))
                for row in snapshot["exposure"]) or
            len({row["article_id"] for row in snapshot["exposure"]}) != len(snapshot["exposure"]) or
            payload["sampler_state"].get("article_ids") != [row["article_id"]
                                                            for row in snapshot["exposure"]] or
            payload["sampler_state"].get("cursor") != payload["training_state"].get("articles_seen") or
            payload["training_state"].get("optimizer_steps", -1) < 0):
        raise ValueError("serving checkpoint train-only provenance/resume metadata differs")
    tokenizer, digest, revision = load_pinned_fast_tokenizer()
    if (payload["backbone"] != {"model_id": core.config.backbone.model_id,
                                  "revision": core.config.backbone.revision,
                                  "weights_sha256": core.config.backbone.expected_weights_sha256,
                                  "stored_in_checkpoint": False} or
            payload["tokenizer"] != {"revision": revision, "sha256": digest}):
        raise ValueError("serving checkpoint pinned backbone/tokenizer differs")
    core.load_state_dict(payload["model_state"], strict=True)
    return V3ServingWorker(core, load_pinned_backbone(core), tokenizer, digest,
                           budget=budget, producer_version="V3_STEP13_SMOKE_DIAGNOSTIC")
