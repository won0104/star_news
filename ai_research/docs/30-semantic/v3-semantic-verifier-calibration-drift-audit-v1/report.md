# #32 Semantic Verifier Calibration Drift & Score-Path Attribution Audit

No training was performed. #30 A verifier is the canonical reference; all primary hybrids use the same A DCE/proposer trunk.

## 결론

`CALIBRATION_DRIFT_SUPPORTED=true`. `PRIMARY_CALIBRATION_DRIFT_GROUP=BOUNDARY_PATH`, `PRIMARY_SCORE_DRIFT_COMPONENT=MIXED`이다. Submodule hybrids는 joint-trained components의 OOD composition일 수 있으므로 functional attribution evidence이지 causal proof가 아니다.

## 사전등록 질문에 대한 답

1. Gold absolute logit median은 A **-1.283921**에서 B **-1.662088**로 이동했고 B-A는 **-0.318907**이다. 따라서 하향 여부는 **true**이다.
2. EVENT/STATEMENT Gold median logit delta는 **-0.381332 / -0.263524**이며 EVENT dominant 판정은 **true**이다.
3. SHORT/MID/LONG delta는 **-0.185059 / -0.271963 / -0.531819**이며 SHORT drift 판정은 **false**이다.
4. A accepted→B rejected Gold rate는 전체 available Gold 기준 **0.157804**, A-accepted 조건부 **0.393743**이다.
5. Recall@1/3 delta는 **-0.000391 / -0.003413**로 relative-ranking gate는 **true**이다. Gold rejection delta **+0.113051**는 이 상대 순위 변화만으로 설명되지 않는다.
6. Margin improved이면서 A accepted→B rejected인 fixed pair는 subspan **95**, superspan **142**, 합계 **237**이다.
7. Margin 유지/개선까지 동반한 common downward shift rate는 **0.166957**이다.
8. Signed mean drift는 validity **+0.164766**, biaffine **-0.424958**이다. Mean/median absolute contribution은 validity **0.648550/0.516840**, biaffine **0.473964/0.433840**이다. Net downward 방향은 biaffine이 운반하지만 absolute validity share가 dominance 기준 0.60 미만이어서 primary component는 **MIXED**이다.
9. BAA multi-view-only delta는 exact **+0.000473**, rejection **-0.015072**, Gold logit **+0.118558**, superspan margin **+0.464085**이다.
10. ABA validity-only delta는 exact **-0.001973**, rejection **+0.023363**, Gold logit **-0.042071**이다.
11. AAB boundary-only delta는 exact **-0.048766**, rejection **+0.121574**, Gold logit **-0.412571**이다.
12. 가장 큰 calibration damage group은 **BOUNDARY_PATH**이다.
13. Superspan margin improvement가 가장 큰 single swap은 **MULTI_VIEW_PROJECTION**이다.
14. Subspan margin improvement가 가장 큰 single swap은 **BOUNDARY_PATH**이다.
15. Constant offset은 exact **+0.028168**, Gold rejection **+0.071974**를 회복했고 ranking unchanged는 **true**이다.
16. CALIBRATION_DRIFT_SUPPORTED는 **true**이다.
17. PRIMARY_CALIBRATION_DRIFT_GROUP은 **BOUNDARY_PATH**이다.
18. 다음 training freeze/preserve 범위는 **{'freeze': ['document_context', 'joint_proposer'], 'preserve_or_freeze_non_target_verifier_groups': ['MULTI_VIEW_PROJECTION', 'VALIDITY_PATH'], 'adapt_with_A_teacher_anchor': 'BOUNDARY_PATH'}**이다.
19. A-teacher calibration anchor 필요 판정은 **true**이다.
20. 다음 training을 SOCKET_CANDIDATE gate 목표로 설계할 근거는 **true**이다. 단 #32 자체나 B checkpoint는 candidate가 아니다.

## 계약 및 검증

- AAA/#30 A parity: **true**; BBB/#31 AB parity: **true**.
- Six checkpoint SHA before/after parity: **true**; protected-source parity: **true**.
- Diagnostic component sum parity max delta: AAA **0**, BBB **0**. Start HEAD: `484c226c8108bd0ca8915caef525dd2db42792dd`.
- No threshold search, label-specific offset, optimizer, training step, checkpoint write, or production source edit was used.

## Machine-readable summary

```text
WORK_STATUS=SEMANTIC_VERIFIER_CALIBRATION_DRIFT_AUDIT_COMPLETE
NEW_MODEL_TRAINING=false
OPTIMIZER_STEP_COUNT=0
A_GOLD_MEDIAN_LOGIT=-1.283920645714
B_GOLD_MEDIAN_LOGIT=-1.662087678909
GOLD_MEDIAN_LOGIT_DELTA=-0.318906977773
EVENT_GOLD_LOGIT_DELTA=-0.381331801414
STATEMENT_GOLD_LOGIT_DELTA=-0.263523578644
A_GOLD_REJECTION=0.599121929663
B_GOLD_REJECTION=0.712173063852
GOLD_REJECTION_DELTA=0.113051134188
A_ACCEPTED_TO_B_REJECTED_GOLD_RATE=0.157803718115
PAIRWISE_IMPROVED_BUT_GOLD_REJECTED_COUNT=237
COMMON_DOWNWARD_SHIFT_RATE=0.166957279861
VALIDITY_SCORE_DRIFT=0.164765614316
BIAFFINE_SCORE_DRIFT=-0.424957849450
AAA_VALIDATION_EXACT=0.372878682892
BAA_VALIDATION_EXACT=0.373351957899
ABA_VALIDATION_EXACT=0.370905757367
AAB_VALIDATION_EXACT=0.324113015520
BBB_VALIDATION_EXACT=0.321599467031
PRIMARY_CALIBRATION_DRIFT_GROUP=BOUNDARY_PATH
PRIMARY_SCORE_DRIFT_COMPONENT=MIXED
MULTIVIEW_ADAPTATION_DRIFT_SUPPORTED=false
SHORT_GOLD_CALIBRATION_DRIFT=false
CALIBRATION_DRIFT_SUPPORTED=true
CONSTANT_OFFSET_EXACT_RECOVERY=0.028167963227
CONSTANT_OFFSET_GOLD_REJECTION_RECOVERY=0.071973881652
NEXT_EXPERIMENT=A_ANCHORED_SCOPE_CALIBRATION_PRESERVING_TRAINING
NEXT_TRAINING_SOCKET_CANDIDATE_TARGET=true
```
