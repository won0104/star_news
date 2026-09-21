# Participant Safe Supervision Contract Audit v1

대상: Construction Gold v3 Round01–03 Curated RC1

## 결과

**READY_FOR_FAIR_AB** — 이 view의 동일한 Event×role mask와 exact evidence 경계 계약을 두 실험이 읽으면, Candidate Classification과 Event-conditioned Span Extraction을 **동일한 semantic completeness/negative 계약 아래 비교할 수 있다**. 이는 공통 aligned/masked subset에서의 준비 완료이며 모든 raw Gold를 학습 가능하다고 하거나 두 loss가 동일하다고 주장하는 판정은 아니다.

기존 A/B v1 runner는 이 새 view에 연결하지 않았다. 기존 5-way Head/모델/학습 코드는 수정하지 않았다. 다음 실험은 A도 독립 binary role로 구현하고 이 view의 mask를 그대로 소비해야 한다. 이번 작업은 tokenizer/label/mask 검사뿐이며 학습·추론·checkpoint 선택은 실행하지 않았다.

## 1. 고정 source와 split

- Gold: `/Users/shinyang-com/Desktop/project-free/ArticleLocal-KG/data/gold/v3_work/round01-03-curated-rc1/curated_gold_rc.json`
- Gold SHA: `0e4d1fa7f1dc0969fb8d8208c67cdd07b037f68b7acef71afd3d02af4ea80002`
- Guideline: `v3-guideline-r02-curated-rc1`
- Guideline SHA: `a3c3012750b27b0ab3946a0156e43012e1b95204787deb73f50e4fbbab5030a1`
- Pilot split SHA: `ebacd02561b018d273f51fe30d7b53f69e3bcdb282b66be8d39c3597ba4466a7`
- Commit: `aaaf2885653b584108e915e06da788b7da4503ea`

Curated RC 150개의 ID/lineage/role review ledger를 source로 확인하고, 기존 pilot_train120/pilot_dev15만 materialize했다. pilot_test15는 제외 ID metadata로만 확인했다. 150개 JSON container 파싱/전체 SHA 확인과 test annotation을 사용한 분석을 구분한다. test text 토큰화·role view·예측·지표 사용은0이다. parent Round01–03 Gold는 label source로 열지 않았으며 기존 보호 목록의 파일 SHA만 확인했다.

Tokenizer는 기존 immutable KF-DeBERTa revision `363b171d71443b0874b0bf9cea053eb5b1650633`, fast tokenizer, sentence 최대128 tokens(특수 token 포함), max_sentences=None이다. 기존 sentence splitter와 ArticleCollator._tokenize를 그대로 호출했으며 실제 `_align_article_span`과 6,752개 Event/filler 정렬 결과를 비교했다. 다른 revision·원문 trim/find/offset 변경은 없다.

## 2. 실행 가능한 공통 계약

- EXHAUSTIVE: exact local filler positive, 나머지 valid local candidate negative. PRESENT-context-only와 ABSENT 모두 local negative를 허용한다. 같은 문장 Event 밖의 filler도 positive다.
- PARTIAL: 확정·정렬 가능한 local filler만 positive, 나머지는UNKNOWN.
- UNRESOLVED/NOT_REVIEWED: 이번 view는 별도 확정 subset을 추론하지 않고 모두 mask한다. evidence는 삭제하지 않는다.
- Event HRR/ambiguity/명시적인 proposition 재검토 보류, Event 단일 문장·token 정렬 실패는 세 role 모두 mask한다.
- local filler 하나라도 unaligned이면 해당 Event×role의 모든 negative를 A/B 모두 mask한다. 다른 확정 aligned positive는 유지할 수 있다. current sentence를 가로지르는 filler도 context-only로 오인하지 않고 negative를 막는다.
- 독립 binary role target/mask를 사용한다. NONE class나 single-label overwrite는 없다.

**Exact negative의 범위:** 사용자가 이번 요청에서 선언한 ‘기록된 evidence 경계를 정확히 추출하는 task’를 적용했다. positive와 겹치지만 경계가 다른 span, 별칭·동일 개체의 다른 mention도 이 exact task에서는 nonmatch negative일 수 있다. 이는 해당 표현이 실제 semantic participant가 아니라는 의미나 Entity/Coreference negative가 아니다. RC guideline의 identity/equivalent-evidence 주의를 삭제하지 않고, supervision view에 이 task scope를 별도로 명시했다. context-only case에서도 의미 상태 PRESENT는 유지한다.

Candidate universe는 source token의 모든 연속 span이다. 이번 계약에서 폭/cap을 새로 선택하지 않았다. 기존 width21 초과 positive ID는 row별 diagnostic으로만 기록하고 제거하지 않았다. 다음 실험에서 cap을 적용한다면 A/B 공통 coverage/mask를 다시 선언해야 하며 빠진 positive를 negative로 바꿀 수 없다.

## 3. Train/dev support

아래 상태 count는 모든 Event×role을 포함하며 실제 학습 허용 mask와 별개다. L=EXHAUSTIVE_WITH_LOCAL_FILLER, C=EXHAUSTIVE_WITH_CONTEXT_ONLY_FILLER, A=EXHAUSTIVE_ABSENT. Uloc은 model sentence를 결정할 수 없거나 filler가 경계를 가로지른 EXHAUSTIVE_UNLOCALIZABLE이며 새 Gold enum이 아니다.

| Split | Role | Events | L | C | A | Partial | Unresolved | Not reviewed | Uloc | Local known+ | Active+ | Safe neg Events | Filler align loss | Multi-role pairs |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| train | ACTOR | 1872 | 788 | 199 | 659 | 18 | 203 | 0 | 5 | 904 | 804 | 1549 | 53 | 9 |
| train | TARGET | 1872 | 1695 | 61 | 64 | 22 | 18 | 0 | 12 | 2035 | 1890 | 1697 | 70 | 16 |
| train | PLACE | 1872 | 294 | 308 | 1233 | 3 | 29 | 0 | 5 | 320 | 295 | 1750 | 9 | 25 |
| dev | ACTOR | 273 | 139 | 18 | 93 | 0 | 23 | 0 | 0 | 143 | 133 | 238 | 8 | 0 |
| dev | TARGET | 273 | 256 | 6 | 6 | 3 | 1 | 0 | 1 | 323 | 296 | 249 | 7 | 4 |
| dev | PLACE | 273 | 43 | 73 | 156 | 1 | 0 | 0 | 0 | 50 | 49 | 257 | 0 | 4 |

Local known+는 confirmed raw evidence지만 upstream/coverage/alignment 때문에 active가 아닐 수 있다. active+가 실제 공통 감독 대상이다. source filler ID·offset·mask 이유는 supervision_view.json에 전부 남겼다. UNRESOLVED role의 raw 목록을 지웠거나 confirmed target으로 자동 승인한 것이 아니다.

| Split | Role | A binary negatives | B endpoint negatives | A UNKNOWN | Same-sentence outside+ | Context+ | Alignment loss reasons |
| --- | --- | --- | --- | --- | --- | --- | --- |
| train | ACTOR | 1159716 | 107134 | 261679 | 199 | 228 | {'NON_EXACT_OR_NON_UNIQUE_TOKEN_BOUNDARY': 53} |
| train | TARGET | 1305174 | 116805 | 115135 | 157 | 119 | {'NON_EXACT_OR_NON_UNIQUE_TOKEN_BOUNDARY': 70} |
| train | PLACE | 1347169 | 123732 | 74735 | 80 | 319 | {'NON_EXACT_OR_NON_UNIQUE_TOKEN_BOUNDARY': 9} |
| dev | ACTOR | 151181 | 15238 | 39058 | 26 | 19 | {'NON_EXACT_OR_NON_UNIQUE_TOKEN_BOUNDARY': 8} |
| dev | TARGET | 161715 | 15800 | 28361 | 24 | 8 | {'NON_EXACT_OR_NON_UNIQUE_TOKEN_BOUNDARY': 7} |
| dev | PLACE | 169144 | 16940 | 21179 | 9 | 76 | {} |

A/B negative 수는 단위가 다르다(span×role vs endpoint×role). 행 단위 semantic permission은 동일하되 수치의 동일함을 요구하지 않는다. sampler/optimizer/loss를 실행한 수치가 아니라 전체 허용 universe의 inventory다.

### 명시적 제외 사유

| Split | Role | Event alignment exclusions | Negative blockers (중복 가능) |
| --- | --- | --- | --- |
| train | ACTOR | {'NO_SINGLE_MODEL_SENTENCE': 11, 'NON_EXACT_OR_NON_UNIQUE_TOKEN_BOUNDARY': 15} | {'COVERAGE_UNRESOLVED': 203, 'PROPOSITION_HRR_OR_AMBIGUOUS': 54, 'LOCAL_POSITIVE_UNALIGNED_MASK_ALL_NEGATIVES': 53, 'EVENT_NO_SINGLE_MODEL_SENTENCE': 11, 'FILLER_LOCALIZATION_UNAVAILABLE': 5, 'PENDING_PROPOSITION_SCOPE_REVIEW': 2, 'EVENT_NON_EXACT_OR_NON_UNIQUE_TOKEN_BOUNDARY': 15, 'COVERAGE_PARTIAL': 18, 'FILLER_UNRESOLVED_OR_AMBIGUOUS': 8, 'PENDING_PROPOSITION_FACTUALITY_REVIEW': 2, 'PENDING_EVENT_IDENTITY_REVIEW': 12, 'PENDING_PROPOSITION_CONTRADICTION_OUTSIDE55': 1} |
| train | TARGET | {'NO_SINGLE_MODEL_SENTENCE': 11, 'NON_EXACT_OR_NON_UNIQUE_TOKEN_BOUNDARY': 15} | {'LOCAL_POSITIVE_UNALIGNED_MASK_ALL_NEGATIVES': 70, 'PROPOSITION_HRR_OR_AMBIGUOUS': 54, 'COVERAGE_UNRESOLVED': 18, 'EVENT_NO_SINGLE_MODEL_SENTENCE': 11, 'FILLER_LOCALIZATION_UNAVAILABLE': 12, 'PENDING_PROPOSITION_SCOPE_REVIEW': 2, 'FILLER_UNRESOLVED_OR_AMBIGUOUS': 13, 'COVERAGE_PARTIAL': 22, 'EVENT_NON_EXACT_OR_NON_UNIQUE_TOKEN_BOUNDARY': 15, 'FILLER_CROSSES_CURRENT_SENTENCE_MASK_ALL_NEGATIVES': 1, 'PENDING_PROPOSITION_FACTUALITY_REVIEW': 2, 'PENDING_EVENT_IDENTITY_REVIEW': 12, 'PENDING_PROPOSITION_CONTRADICTION_OUTSIDE55': 1} |
| train | PLACE | {'NO_SINGLE_MODEL_SENTENCE': 11, 'NON_EXACT_OR_NON_UNIQUE_TOKEN_BOUNDARY': 15} | {'COVERAGE_UNRESOLVED': 29, 'FILLER_UNRESOLVED_OR_AMBIGUOUS': 2, 'LOCAL_POSITIVE_UNALIGNED_MASK_ALL_NEGATIVES': 9, 'PROPOSITION_HRR_OR_AMBIGUOUS': 54, 'EVENT_NO_SINGLE_MODEL_SENTENCE': 11, 'PENDING_PROPOSITION_SCOPE_REVIEW': 2, 'FILLER_LOCALIZATION_UNAVAILABLE': 5, 'EVENT_NON_EXACT_OR_NON_UNIQUE_TOKEN_BOUNDARY': 15, 'PENDING_PROPOSITION_FACTUALITY_REVIEW': 2, 'PENDING_EVENT_IDENTITY_REVIEW': 12, 'COVERAGE_PARTIAL': 3, 'PENDING_PROPOSITION_CONTRADICTION_OUTSIDE55': 1} |
| dev | ACTOR | {'NO_SINGLE_MODEL_SENTENCE': 1} | {'COVERAGE_UNRESOLVED': 23, 'PROPOSITION_HRR_OR_AMBIGUOUS': 13, 'EVENT_NO_SINGLE_MODEL_SENTENCE': 1, 'LOCAL_POSITIVE_UNALIGNED_MASK_ALL_NEGATIVES': 8, 'PENDING_EVENT_IDENTITY_REVIEW': 3} |
| dev | TARGET | {'NO_SINGLE_MODEL_SENTENCE': 1} | {'PROPOSITION_HRR_OR_AMBIGUOUS': 13, 'EVENT_NO_SINGLE_MODEL_SENTENCE': 1, 'FILLER_LOCALIZATION_UNAVAILABLE': 1, 'LOCAL_POSITIVE_UNALIGNED_MASK_ALL_NEGATIVES': 7, 'PENDING_EVENT_IDENTITY_REVIEW': 3, 'COVERAGE_PARTIAL': 3, 'FILLER_UNRESOLVED_OR_AMBIGUOUS': 2, 'COVERAGE_UNRESOLVED': 1} |
| dev | PLACE | {'NO_SINGLE_MODEL_SENTENCE': 1} | {'PROPOSITION_HRR_OR_AMBIGUOUS': 13, 'EVENT_NO_SINGLE_MODEL_SENTENCE': 1, 'COVERAGE_PARTIAL': 1, 'FILLER_UNRESOLVED_OR_AMBIGUOUS': 1, 'PENDING_EVENT_IDENTITY_REVIEW': 3} |

이전 cross-sentence55 packet을 통째로 blacklist하지 않았다. curated lineage상 실제 수정된 Event는 현재 span으로 재정렬하며, 보존한 segmentation artifact는 현재 splitter에 실제로 담기지 않으면 model-local support에서 제외한다. semantic ambiguity는 READY라는 이유로 확정하지 않았다.

## 4. 기존 A NONE0 / B ABSENT 불균형 회귀

기존 실행 artifact에서 A sampled NONE은 train/dev 모두0이다. B의 train 첫 epoch negative endpoint cells는 ACTOR42,172 / TARGET4,458 / PLACE111,322였다. 이 값들은 이미 저장된 결과를 읽은 것으로 재학습 결과가 아니다.

| Split | Role | Curated scope ABSENT-only neg Events | New A=B neg Events | Recovered PRESENT neg Events | ABSENT-only B cells | New B cells |
| --- | --- | --- | --- | --- | --- | --- |
| train | ACTOR | 642 | 1549 | 907 | 43550 | 107134 |
| train | TARGET | 62 | 1697 | 1635 | 4052 | 116805 |
| train | PLACE | 1188 | 1750 | 562 | 85540 | 123732 |
| dev | ACTOR | 92 | 238 | 146 | 5646 | 15238 |
| dev | TARGET | 6 | 249 | 243 | 364 | 15800 |
| dev | PLACE | 145 | 257 | 112 | 9678 | 16940 |

이 표는 **같은 curated label/alignment/보류 mask를 고정하고 negative 허용 조건만 바꾼 counterfactual**이다. 따라서 parent→RC label 변경 효과와 계약 변경 효과를 구별할 수 있다. 과거 모델의 성능이 이만큼 좋아진다는 추정은 하지 않는다. A에서는 전 role ABSENT를 기다리지 않고 각 EXHAUSTIVE role을 독립 감독할 수 있어 NONE0 병목을 구조적으로 제거했다. 자연적인 role별 support 차이와 남은 mask 차이는 여전히 존재한다.

## 5. Same-span multi-role와 boundary factorization

| Split | Raw multi-role groups | Active local multi-role groups |
| --- | --- | --- |
| train | 25 | 22 |
| dev | 4 | 4 |

모든 raw multi-role case와 role ID를 support.json에 보존했다. UNKNOWN role은 mask하지만 다른 role의 확정 positive를 덮어쓰지 않는다.

허용 negative scope에서 **519개**의 non-Gold span은 두 endpoint가 각각 다른 Gold span의 positive endpoint다. A는 이 pair를 binary negative로 표현할 수 있지만 B의 독립 endpoint objective에서는 둘 다positive다. 따라서 B의 cross-pair 문제는 negative 계약 누락이 아니라 factorization의 한계다. 새 verifier/Head를 추가하지 않았다. 같은 completeness 아래 비교 가능하다는 판정과 동일한 supervision 정보량이라는 주장은 구별한다.

## 6. 검증과 보호

- 전체 valid candidate label/mask 4,837,713개, endpoint 450,504개를 검사했다. positive↔negative 충돌0, exact offset 오류0.
- 계약 테스트 16개 PASS: overlap negative, PARTIAL/UNRESOLVED mask, context-only PRESENT, unaligned scope, shared endpoint, multi-role, cross-pair 한계를 포함한다. 테스트 fixture는 메모리 전용이며 synthetic 학습 데이터가 아니다.
- source/보호 파일 109개 SHA 전후 일치. Gold/guideline/model/checkpoint와 기존 untracked 실험 작업 보존.
- 학습·model forward·Round04·commit/push 없음.

## 7. 읽기 및 재현

`supervision_view.json`의 articles[].model_sentences는 tokenizer offset universe, articles[].event_roles는 공통 positive/negative/unknown scope다. local_positive_spans의 **supervision_eligible=true만** positive target으로 사용한다. all_gold_fillers/contextual_positive_spans는 raw support·unsupported 분석용이며 local input에 주입하지 않는다. provenance/coverage/confidence/reason은 audit/mask만을 위한 정보다.

`supervision_contract.py`의 candidate_label과 boundary_labels는 동일 row를 읽는 reference consumer다. 실제 tensor/model runner 연결은 다음 승인된 실험에서 수행해야 한다. negative_scope.allowed=false이면 target0을 active negative로 쓰지 말고 mask=false를 지켜야 한다. candidate boundary나 tokenizer가 바뀌면 기존 SHA view를 조용히 재사용하면 안 된다.

```sh
cd /Users/shinyang-com/Desktop/project-free/ArticleLocal-KG-DeBERTa/training/results/v3-participant-safe-supervision-contract-v1
conda run -n model-test-py312 python validate_view.py -v
conda run --no-capture-output -n model-test-py312 python build_audit.py
```

첫 실행은 검증 후 새 파일을 생성한다. 재현 결과가 기존 immutable output과 다르면 덮어쓰지 않고 중단한다. 산출물 SHA는 artifact_manifest.json을 사용한다. Gold 의미를 다시 판정하는 명령이 아니다.

## 최종 상태

```text
SUPERVISION_CONTRACT_STATUS=READY_FOR_FAIR_AB
GOLD_MODIFIED=false
GUIDELINE_MODIFIED=false
MODEL_MODIFIED=false
TRAINING_EXECUTED=false
PILOT_TEST_USED=false
ROUND04_RESUMED=false
COMMIT_PUSH=false
```

이 결과는 exact evidence task의 공통 감독 준비 상태다. semantic unknown과 model-local 표현 손실은 보존하며, 이 판정으로 production architecture 채택이나 다음 학습을 자동 실행하지 않는다.
