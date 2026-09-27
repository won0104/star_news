# P5 Event identity and P6 Primary feature boundary

## Execution contract

P5 owns an EventFeatureEncoder adapted from the v2.3 release. It encodes **every
retained Event member once before pair routing**, including a singleton for
which the router selects no pair. The request-scoped feature lease holds this
ordered Event tensor. Only routed pairs enter the symmetric encoded-Event pair
branch and the seven explicit channel interactions. The current v3 four-feature
geometry block is removed from P5. The symmetric branch retains v2.3's learned
sentence-distance embedding and consumes the versioned v3 pair source policy.

The pair policy is `V3_EVENT_PAIR_SOURCE_POLICY_15_V2`. It retains exactly
reconstructable Event/Trigger text and source-distance indicators, removes
historical ROLE scalars that depended on the removed Participant→Entity resolver,
and removes the separate v2.3 Event verifier scalar, which has no same-decision
v3 producer. It adds r06 source-grounded **soft** Time evidence: compatible,
incompatible, incomparable, unknown, normalized distance, interval relation,
semantic type, and shared raw evidence. None is a routing gate, acceptance
threshold, or fixed score adjustment. See
`p5-v23-input-mapping-audit-v1.md` for the full producer/formula mapping.
This is a v3 adaptation of the v2.3 structure; numerical v2.3 parity is not
claimed.

The optional channel order is Trigger, ACTOR, TARGET, PLACE, resolved Entity,
Time. Counts and known confidences come from the corresponding source producer.
An absent **Gold/oracle** confidence uses the historical teacher-forced value
`1.0`, marking oracle input. Missing predicted/runtime confidence remains
unknown with an explicit mask and is never replaced by another head's score.

P6 Primary owns no Event encoder. It consumes the **precomputed P5 Event tensor**
from the final cluster lease and learns only its member attention, cluster
aggregation, and final score. Its state dict has no `member_encoder` or copied
EventFeatureEncoder path. ABOUT/CAUSES continue using final-cluster source
channel means and `PairContextV1`; their input contract is unchanged.

## P4→P5 checkpoint migration

The selected P4 checkpoint remains immutable. The explicit migration verifies
its source bytes and old parameter inventory. It copies all common model
parameters exactly, discards the old P4 Event member encoder and pair head, and
fresh-initializes the new P5 Event encoder/pair head from the fixed seed. No
parameter is moved into P6 Primary. The migration artifact binds the selected
P4 checkpoint SHA and current code snapshot. P5/P6 use the new Event-head
checkpoint format and must carry the same migration artifact SHA; older P5/P6
checkpoints cannot resume under the new input schema.

The selected Gold400 P4 recorded one source snapshot byte difference from its
Git HEAD: `training/v3_pretraining/attribution.py`. The recorded SHA is present
unchanged in later commit `291d43649e8f8d4d393e04de79778867c0f8f884`.
Migration accepts only this exact path, hash, original revision, and later
committed revision. All other files must match the P4 HEAD; the checkpoint
itself is not rewritten.

After the implementation snapshot is final, the artifact is produced with:

```text
python -m training.v3_pretraining.event_head_migration \
  --parent <selected-p4-checkpoint.pt> \
  --output <p4-p5-event-feature-migration.json>
```

## Training and evaluation boundary

P5 trains `event_coreference` on its Gold/oracle loss contract. P6 trains
`about`, `causes`, `primary`, and `primary_adapter`; it keeps the P5 Event
encoder frozen. Gold-only dev AP and predicted-source calibration remain
separate. The new head needs fresh P5 training and checkpoint-bound calibration;
the previous Event-coreference threshold or AP cannot be reused. This code
change does not run training, calibrate thresholds, alter the Event pair router
or complete-link closure, or evaluate the test split.
