# Unified Entity mention identity contract

The active V23 path has one Entity identity decision. The Native Entity lane
keeps its T14/C6 bounded candidate selection, native type scoring, and chunked
execution. The Participant lane keeps the Event conditioned B2 endpoint gate,
width constraint, exact coordinate deduplication, and unbounded semantic filler
output. Its Event batch and three role channel computation are shared. B2 is
complete only when each bounded Event chunk has finished exact deduplication,
handed off compact ROLE evidence, and released its Event states, endpoint rows,
alignment cache, and rich decoder provenance before the next chunk. The B2
object lifecycle is an execution bound, never a semantic Top-K.

Accepted Native mentions and B2 role uses meet at exact source coordinates.
An exact ROLE use attaches to one Native mention when that match is unique.
Otherwise it remains a separate mention with internal type `UNKNOWN` (`None`
in the runtime carrier). Overlapping but different spans never merge at this
stage. ASSERTOR source is retained for the later attribution decision and does
not create a coreference mention.

The Entity pair router selects source grounded pairs for the learned
`entity_coreference` fine head. Internal `UNKNOWN` is not a TYPE hard filter:
SOURCE, LEXICAL, and LOCAL postings can retrieve NATIVE–ROLE and ROLE–ROLE
pairs. An unselected pair is `NOT_EVALUATED`, not negative. Complete link
closure runs once. Native evidence determines cluster type; a cluster without
Native evidence becomes `GENERIC` only when projected to a final Entity.
Every ROLE use follows its mention through this closure to the final Entity
ID, including a local singleton when no merge is accepted.

V23 serving now applies an emergency 128-mention safety ceiling after exact
Native/ROLE coalescing and before pair retrieval. It uses the existing
ROLE-first, source-score/coordinate/ID Entity candidate priority; it is not a
learned identity decision or a calibrated quality cutoff. A hit leaves dropped
ROLE uses as `PARTIAL_BUDGET` and records the loss in the audit. Below 128,
the unified inventory and closure are unchanged. The Gold compiler keeps its
complete supervised mention inventory. V3_WINDOW has a separate legacy
candidate budget contract.

Other V23 serving safety ceilings are 65,536 structural Entity and Time rows
each before expensive encoding, and accepted EVENT/STATEMENT 128 and Native
Entity/Time/Trigger 256 each after their existing acceptance gate. These
ceilings leave normal inputs unchanged, use existing cheap/source score
ordering only when exhausted, and never trigger an all-candidate fallback.
The V23 operational default is Event accepted 96, Time accepted 128, Entity
expensive candidates 20,480, and Time expensive candidates 24,576. These
apply after structural candidate union/deduplication but before expensive
Entity/Time scoring, or after existing Event/Time acceptance. The effective
limit is the minimum of the 65,536 emergency ceiling and the operational cap.
An explicit override is reserved for measured shadow runs; it does not change
the source thresholds or structural T14/C6 and T16/C8 candidate policies.

Gold ACTOR and TARGET roles attach to their required exact EntityMention
instead of creating duplicate mention IDs. A grounded PLACE with no exact
Native mention may enter as a separate supervised ROLE mention. An unresolved
PLACE enters as an unsupervised `SPAN_ONLY` mention and is never automatically
a negative coreference pair.

The `role_entity` head, Participant→Entity K64/K32/K16 resolver, and the
preliminary ROLE Entity union are outside this active execution contract.
Historical shadow artifacts remain historical and are not checkpoint or
service policy inputs. `assertor_entity` remains a separate post closure fine
decision. This contract changes the task registry and checkpoint DAG, so
earlier checkpoints and source/pair policy artifacts must fail binding checks
and cannot be silently reused for training or serving.

An ASSERTOR source alone does not create a P3 mention. Its post closure option
builder can select only an Entity produced by the Native or ROLE lanes. If
neither lane produced an Entity, attribution records `NO_ENTITY_OPTIONS`, leaves
the endpoint unresolved, skips `assertor_entity` fine scoring, and emits no
PUBLIC `ASSERTED_BY` edge. It does not create an Assertor-derived mention,
rescue Entity, or additional head. This is a source coverage limit, not an
implicit ASSERTOR Entity promotion. Non-null Gold Assertors already have exact
EntityMention grounding; that Gold guarantee is not a runtime backfill rule.
