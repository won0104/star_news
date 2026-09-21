# V3 Entity Candidate Restriction — Soft-Priority Runtime Promotion v1

## 결론

v2 verifier를 hard Entity restriction으로 재해석하지 않고, 모든 stage-③ EntityMention에
비파괴적 우선순위를 붙이는 stage-⑦ runtime component로 승격했다.

- `HARD_ENTITY_RESTRICTION_READY=false`: v2 internal hard gate 중 TP retention과 FP reduction만
  통과했고 nested mention/pair retention은 실패했다. 이 역사적 판정은 그대로다.
- `SOFT_ENTITY_PRIORITIZATION_READY=true`: stage-③ raw evidence 3,102개를 모두 보존하면서 각
  prediction에 score와 `TIER1_PROMOTED`/`TIER2_EVIDENCE_ONLY`를 1:1로 제공한다.
- TIER2는 false, rejected, deleted Entity가 아니다. 향후 stage-⑥의 bounded rescue 대상이 될 수
  있는 낮은 우선순위 raw evidence다.
- Entity Coreference, Participant Entity Resolution, LocalEntity, canonical MENTIONS edge, Tier2
  rescue pair expansion은 실행하지 않았다.

최종 판정은 `ENTITY_CANDIDATE_PRIORITIZATION_RUNTIME_READY_WITH_LIMITATIONS`이며 다음 공식 work
bundle인 `generic TimeExpression + normalization`으로 이동할 준비가 됐다. 추가 Entity
architecture/loss/distribution 실험은 시작하지 않는다.

## 변경하지 않은 역사적 v2 판정

| v2 internal hard gate | 값 | 기준 | 판정 |
|---|---:|---:|---|
| conditional TP retention | 87.84% | ≥80% | PASS |
| false candidate reduction | 86.94% | ≥50% | PASS |
| nested mention conditional retention | 67.39% | ≥75% | **FAIL** |
| nested pair conditional retention | 43.48% | ≥70% | **FAIL** |

v2 frozen pilot_dev reference의 TP retention 78.05%, FP reduction 84.47%, nested mention 74.07%,
nested pair 61.54%, F1 0.5446도 변경하거나 hard PASS로 다시 쓰지 않았다. 이전 v1/v2 namespace의
artifact는 수정하지 않았다.

## Release-purpose fresh training

v2에서 이미 고정한 아래 설정을 그대로 사용했다.

- architecture/features: detached stage-③ span/L12 context/score/boundary/competition + binary MLP
- data: pilot_train120 전체
- nested-aware replay: 2×
- loss: unweighted BCE
- seed: 1008
- epochs: 정확히 7
- soft-priority threshold: 0.3

Fresh initialization으로 7 epoch를 수행했다. validation selection, epoch reselection, threshold
calibration은 수행하지 않았고 rejected v2 internal checkpoint를 복사하거나 이어 학습하지 않았다.
최종 train loss는 base 0.17438, replay 0.12262다.

Selected release artifact:

- path: `release/kf-deberta-base-kg-extractor/weights/entity_candidate_restriction.pt`
- SHA256: `7ae7813979d2fa30d56dbd915fa8446b0d01b7c39679c5b4fec58e34cb11f0f6`
- size: 944,017 bytes
- strict load: PASS

Stage-③ `entity.pt` SHA256은
`6284ea184e7de57a87890fb89af8f5d14ad8153a4349ba480bcc29e195e44cca`, threshold는 0.7로
그대로다.

## Frozen pilot_dev reference

Fresh release model 완성 후 한 번만 평가했고 설정 feedback에 사용하지 않았다.

| View | TP / FP / FN | P | R | F1 | predictions/article | false/article |
|---|---:|---:|---:|---:|---:|---:|
| stage-③ raw | 442 / 2,660 / 67 | 0.1425 | 0.8684 | 0.2448 | 206.80 | 177.33 |
| stage-⑦ Tier1 diagnostic | 330 / 316 / 179 | 0.5108 | 0.6483 | 0.5714 | 43.07 | 21.07 |

Fresh release reference의 conditional TP retention은 74.66%, FP reduction은 88.12%, recoverable
nested mention retention은 55.56%, nested pair joint retention은 23.08%다. 이는 soft priority의
관찰값이며 v2 hard gate를 다시 판정하거나 완화하는 데 사용하지 않았다. Tier2의 2,456개 mention은
계속 유효한 raw evidence로 남는다.

## Runtime contract와 density

새 canonical runtime ID는
`eventframe_runtime_candidate_v3_entity_soft_priority_freeze`다. 각 decision은 다음을 보존한다.

- `entity_prediction_id`
- `promotion_score`
- `priority_tier = TIER1_PROMOTED | TIER2_EVIDENCE_ONLY`
- `verifier_checkpoint_sha`
- `runtime_config_id`
- `responsibility = "⑦ 후보 제한부"`

정책 불변식은 다음과 같다.

- `hard_deletion_authorized=false`
- `hard_identity_eligibility_gate_authorized=false`
- `raw_entity_evidence_preserved=true`
- `TIER2_RESCUE_POLICY=DEFERRED_TO_ENTITY_IDENTITY_INTEGRATION`

pilot_dev15 runtime 합계는 raw 3,102, Tier1 646, Tier2 2,456이다. 평균은 각각
206.80/43.07/163.73 per article이다. detached input feature 생성부터 competition/MLP score까지의
verifier runtime delta는 평균 0.0826초/article, 전체 canonical runtime은 평균 3.8331초/article였다.

향후 계산량 참고용 pair upper bound는 raw 539,102개(35,940.13/article), Tier1-only 23,289개
(1,552.60/article)다. 약 95.68% 감소 가능성을 보이지만 이번 작업에서 어느 pair도 실제 생성하지
않았고 Tier1을 유일한 stage-⑥ eligibility universe로 고정하지도 않았다.

## Regression, graph, release smoke

같은 새 runtime ID와 같은 model instance에서 stage-⑦만 끈 control을 사용해 독립변수를 격리했다.
stage-③ raw EntityMention, Event, Statement, Trigger, StatementType, B2는 pilot_dev 15/15 exact
parity다. runtime serialization도 deterministic이다. 별도 프로세스에서 저장한 역사적 baseline은
runtime-dependent derived ID를 제외한 구조가 15/15 동일했고 float32 CUDA 최대 절대 점수 차이는
1.1743e-5(허용 5e-5)였다.

Graph replay 결과:

- raw EntityMention evidence: 3,102/3,102 보존
- priority metadata: 3,102/3,102 보존(Tier1/Tier2 모두 포함)
- raw participant: 163 보존
- LocalEntity/fake Entity/MENTIONS edge/dangling reference: 모두 0
- schema/serialization: 15/15 PASS, deterministic
- Event/Statement/Trigger/StatementType/B2 regression: 0
- Entity Coreference/Participant Entity Resolution: `NOT_RUN`

Release directory만 임시 복사한 GPU smoke에서 config load, component SHA 검증, pinned external base
load, sample inference, priority completeness, JSON serialization을 모두 통과했다. training results에
대한 inference dependency는 없다.

Canonical `tests/` suite는 276 tests PASS, 2 skip이다. 두 skip은 기존 historical ignored checkpoint와
optional Streamlit 부재다. 새 정책/weight/runtime/graph targeted suite 33건과 관련 historical
regression suite 19건도 모두 PASS다. 참고로 repository root 전체의 non-canonical training experiment
discovery는 ignored transient `compiled_supervision.pt`가 없는 과거 participant experiment 한 건에서
setup error였으며 현재 work unit과 무관하다. cache를 만들거나 Git에 추가해 이를 우회하지 않았다.

## Handoff

Source of truth는 release runtime config, 두 selected Entity weight, release manifests와 이 directory의
JSON artifact다. 다음 작업은 `generic TimeExpression + normalization`이다. Entity identity 작업이
향후 별도로 승인되면 Tier1은 기본 우선순위 pool, Tier2는 구조적 nesting/overlap과 local competition,
promotion score, deterministic top-k/cap을 감사한 뒤 bounded rescue pool로 사용할 수 있다. 현재는
그 rescue 정책과 pair computation 모두 deferred다.

보호 상태:

- Curated Gold/guideline/Round04: 수정·재개하지 않음
- stage-③ architecture/checkpoint/threshold/candidate enumeration: 변경하지 않음
- B2/PLACE gate 및 Entity feature: 사용하지 않음
- pilot_test/original 1K dev/test: 사용하지 않음
- HF remote/Notion: 수정하지 않음
- intermediate/rejected checkpoint와 cache: release/Git 대상 아님
