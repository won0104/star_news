"""r05.3 compiler와 architecture가 공유하는 Gold 비의존 task 이름·의존성."""

from __future__ import annotations

from dataclasses import dataclass


SPAN_TASKS = ("semantic_proposer", "semantic_boundary", "semantic_validity", "trigger",
              "participant", "entity_mention", "time_mention", "assertor_source")
PAIR_TASKS = ("entity_coreference", "event_coreference", "event_time",
              "assertor_entity", "about", "causes")
CLASS_TASKS = ("statement_type", "time_normalization")
HEAD_TASKS = SPAN_TASKS + PAIR_TASKS + CLASS_TASKS + ("primary",)
TRAINING_PHASES = ("extraction", "entity_role_time_attribution_sources",
                   "entity_identity", "entity_role_time_attribution",
                   "event_identity", "cluster_consumers")

# Assertor source precedes Entity identity; Assertor→Entity option validation uses
# the trained identity checkpoint. This is a staged runtime dependency, not a
# new ontology dependency of the assertor_entity head.
# Each later phase starts only after its preceding checkpoint has been sealed.
PHASE_TASKS = {
    "extraction": ("semantic_proposer", "semantic_boundary", "semantic_validity",
                   "trigger", "participant", "entity_mention", "time_mention",
                   "statement_type"),
    "entity_role_time_attribution_sources": ("event_time", "time_normalization",
                                             "assertor_source"),
    "entity_identity": ("entity_coreference",),
    "entity_role_time_attribution": ("assertor_entity",),
    "event_identity": ("event_coreference",),
    "cluster_consumers": ("about", "causes", "primary"),
}
if tuple(PHASE_TASKS) != TRAINING_PHASES or set(sum(PHASE_TASKS.values(), ())) != set(HEAD_TASKS):
    raise AssertionError("staged task inventory differs from head registry")


@dataclass(frozen=True, slots=True)
class TaskDefinition:
    name: str
    phase: str
    dependencies: tuple[str, ...]
    representation: str


TASK_DEFINITIONS = {
    row.name: row for row in (
        TaskDefinition("semantic_proposer", "extraction", (), "L8+DCE"),
        TaskDefinition("semantic_boundary", "extraction", ("semantic_proposer",), "L8+DCE+RAW"),
        TaskDefinition("semantic_validity", "extraction", ("semantic_proposer",), "L8+DCE+RAW"),
        TaskDefinition("trigger", "extraction", ("semantic_proposer",), "L8"),
        TaskDefinition("participant", "extraction", ("semantic_proposer",), "L8+DCE+Event"),
        TaskDefinition("entity_mention", "extraction", (), "L12+DCE+exact existence/type"),
        TaskDefinition("time_mention", "extraction", (), "L10+DCE+exact decision"),
        TaskDefinition("statement_type", "extraction", ("semantic_proposer",), "L8+DCE+Statement"),
        TaskDefinition("event_time", "entity_role_time_attribution_sources", ("semantic_proposer", "time_mention"), "directed Event/Time pair"),
        TaskDefinition("time_normalization", "entity_role_time_attribution_sources", ("time_mention",), "textual Time"),
        TaskDefinition("assertor_source", "entity_role_time_attribution_sources", ("semantic_proposer",), "Statement/source span"),
        TaskDefinition("assertor_entity", "entity_role_time_attribution", ("assertor_source", "entity_mention"), "directed Statement/Entity pair"),
        TaskDefinition("entity_coreference", "entity_identity", ("entity_mention", "participant"), "symmetric unified mention pair"),
        TaskDefinition("event_coreference", "event_identity", ("semantic_proposer", "trigger", "participant",
                                                     "entity_coreference", "event_time",
                                                     "time_normalization"), "shared Event/role/Entity/Time symmetric pair"),
        TaskDefinition("about", "cluster_consumers", ("event_coreference", "semantic_proposer"), "Statement/EventCluster directed pair"),
        TaskDefinition("causes", "cluster_consumers", ("event_coreference",), "EventCluster/EventCluster directed pair"),
        TaskDefinition("primary", "cluster_consumers", ("event_coreference", "semantic_proposer"), "EventCluster∪Statement shared comparison"),
    )
}
if set(TASK_DEFINITIONS) != set(HEAD_TASKS):
    raise AssertionError("task registry and target compiler names differ")
