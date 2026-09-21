# Canonical Span Representation V3 Architecture Freeze (#38)

## 결론

`CANONICAL_SPAN_REPRESENTATION_V3`는 하나의 label-independent span 표현을 공유하고,
Semantic Eligibility와 Boundary Exactness를 독립 supervision·logit·threshold·decision으로
분리한 candidate-local 모델이다. 전체 trainable parameter는 **760,226**개이며,
모든 architecture acceptance check가 통과했다.

이 작업은 architecture/supervision/decoder contract freeze다. Full training, optimizer step,
threshold 선택, Validation24/Round04 평가, 성능 비교를 수행하지 않았다.

## 검증 사실과 결정

1. **왜 #35 responsibility split 자체는 유지했나?** Semantic validity와 boundary/scope를 같은 scalar와 supervision에 넣었을 때 발생한 책임 충돌을 피하고, #35~#37에서 두 판정의 독립성이 필요하다는 근거가 유지됐기 때문이다.
2. **왜 V2 Scope architecture는 canonicalize하지 않았나?** ScopeV2에는 group, relation-aware attention, delta region, priors, duplicated views가 누적되어 candidate-local exact-boundary 판정 책임보다 넓었다. V3에서는 이를 모두 제거했다.
3. **V3의 한 문장 정의는?** 하나의 label-independent canonical span representation 위에 semantic eligibility와 boundary exactness 두 absolute decision head를 둔 모델이다.
4. **V3에서 공유되는 것은 무엇인가?** TokenFusion과 CanonicalSpanEncoder가 만드는 `z_span`이다.
5. **분리되는 것은 무엇인가?** supervision, output scalar, private head, 향후 threshold, downstream gate다.
6. **RAW와 DCE는 정확히 어디서 fuse되는가?** `CanonicalTokenFusion`에서 각각 256차원으로 projection한 뒤 더하고 LayerNorm한다. 직접 fusion은 한 번이다.
7. **DCE_LOCAL은 왜 제거했나?** DCE contextual token이 이미 upstream context를 포함하며 별도 view는 같은 의미의 중복 입력이기 때문이다.
8. **z_span은 어떤 네 component로 구성되는가?** fused start, fused end, attentive fused content, 단일 32차원 width embedding이다.
9. **z_span은 label-dependent인가?** 아니다. `[B,Q,256]`의 label-independent 표현이다.
10. **EVENT/STATEMENT label은 어디에 들어가는가?** 64차원 label embedding이 두 private head 입력에만 들어간다.
11. **SemanticEligibilityHead는 정확히 무엇을 판단하나?** span content가 해당 label의 proposition으로 의미적으로 성립 가능한지를 candidate-local absolute logit으로 판단한다.
12. **BoundaryExactnessHead는 정확히 무엇을 판단하나?** candidate의 start/end가 해당 label proposition의 annotated complete boundary인지 absolute logit으로 판단한다.
13. **left/right boundary transition은 어떻게 정의했나?** `h_start - h_(start-1)`와 `h_(end-1) - h_end`이며 문장 가장자리에서는 learned BOS/EOS vector를 outside 값으로 쓴다.
14. **ScopeGroupBuilder는 남아 있는가?** V3 model/target/decoder에는 없다. 과거 V2 구조 audit에만 읽기 전용으로 언급된다.
15. **candidate-to-candidate attention이 존재하는가?** 없다.
16. **delta-region이 존재하는가?** 없다.
17. **validity_logit/proposal_score prior가 존재하는가?** 없다. proposal score는 upstream candidate generation 책임으로만 남는다.
18. **width 정보는 몇 종류 사용되는가?** `min(width, 96)`의 단일 width embedding 한 종류다.
19. **semantic target은 어떻게 정의하는가?** exact confirmed Gold는 positive, 명시적으로 reviewed된 `SEMANTIC_NEGATIVE`만 negative, 나머지는 mask다.
20. **boundary target은 어떻게 정의하는가?** exact-any-Gold는 positive, 같은 article/sentence/label Gold와 겹치지만 exact가 아니면 negative, 비겹침은 mask다.
21. **boundary wrong이 semantic negative를 의미하는가?** 아니다. 별도 semantic authority가 없으면 semantic mask다.
22. **multi-Gold가 있을 때 exact positive precedence는?** 하나라도 exact면 다른 Gold와 non-exact overlap하더라도 boundary positive다.
23. **nested/overlapping Gold를 둘 다 출력 가능하게 표현하는가?** 가능하다. model-level suppression 없이 각 candidate가 두 gate를 독립 통과하며 exact identity만 dedupe한다.
24. **semantic/boundary loss의 gradient ownership은?** 두 loss 모두 TokenFusion/CanonicalSpanEncoder를 shaping하고 각자의 private head에만 흐른다. semantic→boundary와 boundary→semantic 경로는 0이며 frozen upstream은 parameter tree 밖이다.
25. **weighted loss sum을 향후 사용하는가?** 아니다. #39 계약은 semantic/boundary 1:1 alternating update다.
26. **V3 총 parameter count는?** **760,226**개다.
27. **A/V2 대비 얼마나 작아졌는가?** A 대비 1,120,127개(59.57%), V2 total 대비 1,319,332개(63.44%) 감소했다.
28. **candidate order/neighbor 존재가 score를 바꾸는가?** 바꾸지 않았다. smoke의 최대 절대 차이는 `4.291534423828125e-06`이고 leakage는 `0`다.
29. **TRAIN196 target census는?** 3-seed 합계 Semantic POS=16,175, NEG=626,775, MASK=421,816; Boundary POS=16,175, NEG=378,198, MASK=670,393다. Gold proposal coverage는 seed 1008: proposed 5384, not proposed 108, seed 2008: proposed 5400, not proposed 92, seed 3008: proposed 5391, not proposed 101다.
30. **UNDER/OVER/shift/partial-overlap 분포는?** UNDER=124,756, OVER=10,682, LEFT_SHIFT=91,474, RIGHT_SHIFT=75,346, PARTIAL=42,884, BRIDGE/MULTI=33,056, OTHER=0다. R3/R4/R5 reason mapping은 frozen cache에 보존되지 않아 추론하지 않았다.
31. **Gold-Gold containment 구조는 몇 개인가?** seed 중복 없이 multi-Gold sentence/label 835개, nested pair 120개, overlap pair 157개, direct-containment pair 117개다.
32. **어떤 V2 feature가 완전히 제거됐나?** DCE_LOCAL, sentence/document concat, duplicated five-view, raw/normalized width scalar, absolute positions, full outside vectors, validity/proposal priors, containment/pair/delta-region features, set attention, group utility, pairwise/biaffine scorer, local-max suppression을 제거했다.
33. **ARCHITECTURE_SIGNATURE_SHA256은?** `90e6e70d5ced536dba975621dfaeb68e611e77ff64d82e015654175f416686a9`다.
34. **ARCHITECTURE_READY_FOR_CONTROLLED_TRAINING인가?** `true`다.
35. **#39에서 source를 바꾸지 않고 TRAIN196 controlled evaluation을 실행할 수 있는가?** 가능하다. 이 freeze의 source와 manifest signature를 그대로 검증한 뒤 alternating schedule을 실행하면 된다.

## Gradient smoke

- Semantic backward: `{'TokenFusion': 1.3366260029270702, 'CanonicalSpanEncoder': 1.7691630535763523, 'SemanticEligibilityHead': 1.2722712318283982, 'BoundaryExactnessHead': 0.0, 'BOS_EOS_boundary_vectors': 0.0}`
- Boundary backward: `{'TokenFusion': 1.608570236523834, 'CanonicalSpanEncoder': 1.0988175358899188, 'SemanticEligibilityHead': 0.0, 'BoundaryExactnessHead': 2.655774995024051, 'BOS_EOS_boundary_vectors': 0.03216493378006505}`
- Optimizer step: `0`

## Machine-readable summary

```text
WORK_STATUS=CANONICAL_SPAN_REPRESENTATION_V3_ARCHITECTURE_COMPLETE
FULL_TRAINING=false
OPTIMIZER_STEP_COUNT=0
PERFORMANCE_SELECTION=false
ARCHITECTURE_NAME=CANONICAL_SPAN_REPRESENTATION_V3
RAW_DCE_FUSION_COUNT=1
DCE_LOCAL_DIRECT_PATH=false
FUSED_HIDDEN=256
Z_SPAN_HIDDEN=256
WIDTH_EMBED_DIM=32
LABEL_EMBED_DIM=64
SPAN_ATTENTION_HIDDEN=128
DROPOUT=0.1
TOTAL_V3_PARAMETER_COUNT=760226
TRAIN_SEMANTIC_POSITIVE=16175
TRAIN_SEMANTIC_NEGATIVE=626775
TRAIN_SEMANTIC_MASKED=421816
TRAIN_BOUNDARY_POSITIVE=16175
TRAIN_BOUNDARY_NEGATIVE=378198
TRAIN_BOUNDARY_MASKED=670393
NESTED_GOLD_PAIR_COUNT=120
ARCHITECTURE_SIGNATURE_SHA256=90e6e70d5ced536dba975621dfaeb68e611e77ff64d82e015654175f416686a9
ARCHITECTURE_READY_FOR_CONTROLLED_TRAINING=true
NEXT_EXPERIMENT=CANONICAL_SPAN_V3_TRAIN196_CONTROLLED_EVALUATION
```
