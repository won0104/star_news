# v3 frozen KF-DeBERTa run-local cache

## 결론

반복 backbone 실행은 학습상 필요가 아니라 실행 경로에 frozen feature cache가
연결되지 않았기 때문에 발생했다. 현재 경로는 source view별 최초 요청에서만
KF-DeBERTa를 실행하고, detached FP32 CPU L8/L10/L12를 같은 run의 train,
Gold-oracle evaluation, predicted cascade, strict-reload evaluation이 공유한다.
`DocumentContextEncoder`부터는 optimizer step마다 반드시 다시 계산한다.

## 확인한 기존 실행 경로

중앙 경로는 다음과 같았다.

`TargetCompiler` → `TargetCollator`/`SourceWindowBatch.article_view()` →
`FrozenBackboneFeatureBuilder.build()` → frozen KF-DeBERTa → L8/L10/L12 →
`V3Core.forward_shared()` → `DocumentContextEncoder` →
`CandidateSpanEncoder`/`ExactSourceSpanBridge` → task heads.

Backbone parameter는 `requires_grad=False`이고 optimizer inventory에 없으며,
builder가 `eval()`과 `torch.no_grad()`를 적용한다. 반면 기존
`FrozenSourceViewKey`는 identity 계약만 있었고 `V3Trainer`와 serving worker의
실제 `build()` caller에 cache lookup/store가 없었다. 따라서 r06 train73의 네
deterministic sweep은 같은 73개 all-window source view에 대해 training backbone
forward를 292회 실행했다.

`checkpoint.py::source_cache_key()`도 compile manifest용 scalar digest를 만들었지만
feature store/lookup caller는 아니었다. 실행 cache에는 새 병렬 article-ID key를
만들지 않고 기존 `FrozenSourceViewKey`를 source tensor·preprocessing·sentence
split·backbone identity까지 보강해 사용했다.

## 변경된 실행 경로와 경계

현재 실행은 다음 순서다.

1. CPU에서 deterministic source windows와 `FrozenSourceViewKey`를 만든다.
2. run-local CPU cache를 조회한다.
3. miss이면 frozen backbone을 한 번 실행하고 L8/L10/L12와 validation mask를
   detach/clone하여 원 dtype 그대로 CPU에 저장한다.
4. hit이면 해당 article/view의 세 layer만 execution device로 복사한다.
5. miss와 hit 모두 `DocumentContextEncoder`부터 새 autograd graph를 만든다.

Cache 허용 범위는 frozen KF-DeBERTa의 L8/L10/L12뿐이다. DCE output,
candidate/exact-span representation, semantic/task feature, logit은 저장하지 않는다.
CPU cache backend는 한 backbone object에 bind되어 다른 producer instance와의
stale reuse를 fail-closed한다. 정상 runner 종료에서는 cache를 명시적으로
release하고 checkpoint/model state에는 feature tensor를 기록하지 않는다.

## Cache key 계약

`FrozenSourceViewKey`는 다음을 모두 묶는다.

- article version과 source content SHA256
- backbone model ID, immutable revision, expected weights SHA256
- required layers `(8, 10, 12)`와 inference dtype
- pinned tokenizer SHA256
- source preprocessing, 원문 sentence split, window/layout, source-view contract
- ordered window identity digest
- 실제 input IDs, attention mask, source-token mask, token-offset digest

Hit 시에도 content와 실제 one-article input/mask/offset digest를 다시 대조한다.
계약이나 tensor shape/dtype/mask가 다르면 stale entry를 사용하지 않고 miss로
처리한다. 동일 cache를 다른 backbone object에 연결하는 것은 오류다.

## Cache value 계약

Entry는 detached contiguous CPU tensor인 L8/L10/L12, attention mask,
sentence mask와 함께 input IDs, source-token mask, sentence position,
token/source offset metadata를 가진다. 매 caller는 기존 deterministic
`ArticleBatch`를 계속 전달하고 cache entry와 exact equality를 검사한다. Ordered
window identity도 key가 검증한다. 따라서 downstream API는 바뀌지 않았고 cache에
accelerator tensor나 autograd graph가 남지 않는다.

## 실제 caller 연결

- training과 일반 evaluation: `V3Trainer._frozen_article_view()`
- selection/Gold-oracle/full-universe relation evaluation: 같은 trainer cache
- predicted cascade: scale runner가 같은 cache를 `V3ServingWorker`에 주입
- strict reload evaluation: fresh core만 만들고 같은 frozen producer/cache 재사용

Serving은 cache hit에서도 DCE를 한 번 실행한다. 실제 worker fixture에서 첫 요청은
backbone/DCE `1/1`, 같은 source의 두 번째 요청은 `0/1`이었다.

## Parity와 비용 측정

Repository-declared `model-test-py312`에서 최종 코드를 검증했다.

- 동일 view L8/L10/L12: exact equality, `max_abs_diff=0`
- 실제 trainer의 20 loss channel: cold miss와 hit exact equality
- Primary score: exact equality
- 3-step downstream SGD trajectory: cached/uncached loss, decode, 최종 parameter
  tensor exact equality
- cache tensor: CPU, `requires_grad=False`, `grad_fn=None`, inference tensor 아님
- frozen backbone gradient: 없음; DCE gradient: finite/nonzero
- 실제 serving worker: second request backbone 0회, DCE 1회, PUBLIC/acceptance/
  candidate trace exact equality
- synthetic 3-view × 4-sweep: backbone `12 → 3`, hit/miss `9/3`

실제 pinned backbone을 MPS에서 optimizer/backward 없이 한 기사로 측정한 값은
[benchmark JSON](v3-frozen-feature-cache-benchmark.json)에 있다. Cold miss 전체는
1204.26 ms, hit 전체는 645.33 ms였고, backbone feature build 314.83 ms,
lookup 1.24 ms, CPU→MPS transfer 호출 0.89 ms였다. 20개 loss의 최대 차이는
0이었다. 이는 단일 view의 engineering 측정이며 전체 serving latency 추정치가
아니다.

기존 train73 schedule에서 training forward count는 구조적으로 `292 → 73`이다.
업데이트된 runner는 train scope에서 miss 73, hit 219, forward 73이 아니면
fail한다. 이번 변경 검증을 위해 73-step 학습을 다시 실행하지는 않았다.

## 메모리 trade-off

MPS 진단 entry 하나(28 windows)는 CPU 33,124,028 bytes였고 accelerator resident
cache entry는 0이었다. r06 train73의 실제 tokenizer/layout inventory는 2,952
windows이므로 동일 FP32 계약의 training cache tensor payload는 3,492,218,952
bytes(약 3.25 GiB)다. 평균은 기사당 약 47.8 MB이고 최대 window 수는
190이다. CPU RAM 증가가 작지 않으므로 후속 최적화에서는 bounded/persistent
backend를 별도 결정할 수 있지만, 이번 단계에서는 eviction, dtype compression,
disk persistence를 추가하지 않았다.

MPS current allocation은 진단 전후 784,068,864 → 784,079,104 bytes였다. Driver
allocation 증가는 MPS allocator의 실행 cache까지 포함하며 frozen feature가 MPS에
상주했다는 뜻이 아니다. 이 환경에는 MPS peak 전용 API가 없어 current/driver
값만 기록했다. Process peak RSS는 모델 load가 이미 만든 peak 때문에 전후 동일한
1,171,537,920 bytes였으며 cache의 실제 CPU 증분은 entry byte count를 권위값으로
사용한다.

## 검증 결과와 제한

- focused cache/trainer/serving/relation/architecture tests: 9 PASS
- architecture key/boundary regression: PASS
- compileall: PASS
- broader `test_v3_harness + step04 runtime + step07`: 26 PASS, 4 FAIL

마지막 네 실패는 cache hit 이전의 첫 online training call에서도 발생하는 기존
D8 gradient-clip tolerance 3건과 stale trainable-parameter-count 기대값 1건이다.
이번 변경은 parameter inventory나 clipping 코드를 수정하지 않았다. 이를 숨기기
위해 unrelated contract를 변경하지 않았다.

남은 최적화 여지는 CPU cache 용량 정책, host-to-MPS transfer overlap/pinning,
그리고 검증된 persistent backend다. 모두 correctness와 별도 승인이 필요한 후속
범위이며 이번 구현에는 포함하지 않았다.
