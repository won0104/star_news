"""r05.3 compiler와 architecture가 공유하는 Gold 비의존 task 이름·의존성."""

from __future__ import annotations

from dataclasses import dataclass


SPAN_TASKS = ("semantic_proposer", "semantic_boundary", "semantic_validity", "trigger",
              "participant", "entity_mention", "time_mention", "assertor_source")
PAIR_TASKS = ("entity_coreference", "event_coreference", "role_entity", "event_time",
              "assertor_entity", "about", "causes")
CLASS_TASKS = ("statement_type", "entity_priority", "time_normalization")
HEAD_TASKS = SPAN_TASKS + PAIR_TASKS + CLASS_TASKS + ("primary",)
TRAINING_PHASES = ("extraction", "entity_role_time_attribution", "identity", "cluster_consumers")


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
        TaskDefinition("entity_mention", "extraction", (), "L12+DCE"),
        TaskDefinition("time_mention", "extraction", (), "L10+DCE"),
        TaskDefinition("statement_type", "extraction", ("semantic_proposer",), "L8+DCE+Statement"),
        TaskDefinition("entity_priority", "entity_role_time_attribution", ("entity_mention",), "retained Entity boundary"),
        TaskDefinition("role_entity", "entity_role_time_attribution", ("participant", "entity_mention"), "directed role/entity pair"),
        TaskDefinition("event_time", "entity_role_time_attribution", ("semantic_proposer", "time_mention"), "directed Event/Time pair"),
        TaskDefinition("time_normalization", "entity_role_time_attribution", ("time_mention",), "textual Time"),
        TaskDefinition("assertor_source", "entity_role_time_attribution", ("semantic_proposer",), "Statement/source span"),
        TaskDefinition("assertor_entity", "entity_role_time_attribution", ("assertor_source", "entity_mention"), "directed Statement/Entity pair"),
        TaskDefinition("entity_coreference", "identity", ("entity_mention", "role_entity"), "symmetric Entity pair"),
        TaskDefinition("event_coreference", "identity", ("semantic_proposer", "trigger", "participant",
                                                     "entity_coreference", "role_entity", "event_time",
                                                     "time_normalization"), "shared Event/role/Entity/Time symmetric pair"),
        TaskDefinition("about", "cluster_consumers", ("event_coreference", "semantic_proposer"), "Statement/EventCluster directed pair"),
        TaskDefinition("causes", "cluster_consumers", ("event_coreference",), "EventCluster/EventCluster directed pair"),
        TaskDefinition("primary", "cluster_consumers", ("event_coreference", "semantic_proposer"), "EventCluster∪Statement shared comparison"),
    )
}
if set(TASK_DEFINITIONS) != set(HEAD_TASKS):
    raise AssertionError("task registry and target compiler names differ")
