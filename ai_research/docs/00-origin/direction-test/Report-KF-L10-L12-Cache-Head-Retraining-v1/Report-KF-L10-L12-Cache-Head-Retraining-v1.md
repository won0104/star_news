# KF L10/L12 cache + shared context/token·span Head 재학습

- 실험일: 2026-09-02
- 상태: 완료
- 장비: NVIDIA GeForce RTX 4050 Laptop GPU
- 목적: `KF L10/L12 cache → shared context 및 핵심 token/span Head 재학습` 후 legacy KLUE/RoBERTa 표현과 비교
- machine-readable 결과: `artifacts/kf-layer-head-ablation-v2/summary.json` (Git 제외)

## 결론

사용자의 가설은 **핵심 token/span 과제에서는 맞았다.** Frozen KF-DeBERTa 표현에 맞춰 shared context와 Head를 처음부터 다시 학습하자, 이전의 frozen linear probe와 전혀 다른 결과가 나왔다.

- 4개 token/span Head 평균 test macro-F1은 legacy L12 `0.5496`에서 KF L10 `0.8260`, KF L12 `0.8229`로 올랐다. KF L10 기준 `+0.2765` (`+27.65%p`)다.
- exact character-span micro-F1도 entity `0.2557 → 0.5577/0.6243`, time `0.1361 → 0.8613/0.8212`, trigger `0.6331 → 0.8918/0.8880`으로 개선됐다.
- 그러나 sentence routing test macro-F1은 legacy L12 `0.8777`, KF L10 `0.8191`, KF L12 `0.7478`이었다. DeBERTa 최종 층 하나로 모든 task를 교체하는 결론은 지지되지 않는다.
- KF 내부에서는 L10이 4-task 평균과 time/semantic/trigger exact span에, L12가 entity exact span에 유리했다. 따라서 새 구조의 기본값은 **task-aware layer adapter/mix**여야 한다.

현재 증거로 내릴 수 있는 결정은 다음과 같다.

1. `ArticleLocal-KG-DeBERTa`의 token/span 기반 표현으로 KF-DeBERTa를 채택한다.
2. 단일 L12 고정 출력은 채택하지 않는다. L10을 token/span 기본 후보로 두고 entity에는 L12 또는 learned mix를 함께 시험한다.
3. sentence selection/routing은 hard gate로 쓰지 않는다. routing 전용 layer mix와 Head를 별도로 다시 검증한다.
4. pair, argument, coreference, relation, end-to-end LocalKG 성능은 이번 실험으로 판정하지 않는다.

## 확인한 실험 계약

### 입력과 모델

| 항목 | 값 |
|---|---|
| Gold | `gnews-1k-construction-gold-v2.0` |
| Gold SHA-256 | `0757a6be7ca35fd3d9ca742fca4e0324e15620077d255cc3be935dbab2def212` |
| KF checkpoint | `kakaobank/kf-deberta-base` |
| KF revision | `363b171d71443b0874b0bf9cea053eb5b1650633` |
| KF weights SHA-256 | `3cd6cd7811b3c9190e97cae7eb41571c2bc0076431baae7d41d449a8c1c18c6c` |
| 비교 표현 | legacy L12, KF L10, KF L12 |
| backbone 상태 | frozen cache |
| PyTorch/CUDA | `2.11.0+cu128` / CUDA `12.8` |
| split/model init seed | `41` / `1008` |

KF L10/L12는 동일 checkpoint의 `output_hidden_states`에서 각각 뽑았다. 기존 `ArticleLocal-KG` cache serializer를 사용하되 결과는 `DirectionTest/artifacts`에 격리했다.

| cache | 기사/문장 | truncated 문장 | payload | 생성 시간 | fingerprint |
|---|---:|---:|---:|---:|---|
| KF L10 | 1,000 / 27,403 | 50 | 10.15 GiB | 303.8초 | `20b17ad3...add71f` |
| KF L12 | 1,000 / 27,403 | 50 | 10.15 GiB | 313.7초 | `1c11f285...071e55` |

### 공정 비교 범위

각 variant는 같은 seed로 기존 shared context/Head 구조를 새로 초기화했다. 먼저 `sentence_projection` shared routing context를 학습하고, 그 상태를 이어받아 token context fusion과 다음 네 Head를 학습했다.

- `entity_mention`
- `time_mention`
- `semantic_span`
- `event_trigger`

Routing은 전체 1,000기사를 같은 `800/100/100` split으로 평가했다. Token/span은 tokenizer 차이로 비교 가능 집합을 먼저 교집합으로 고정했다.

- KF에서 정확한 source-token 정렬이 되지 않은 고유 기사 34개 제외
- 기록된 정렬 issue: `SPAN_HAS_NO_SOURCE_TOKEN` 16건, `SPAN_TOKEN_BOUNDARY_MISMATCH` 40건
- 공통 기사 966개를 같은 `773/97/96` train/dev/test로 사용
- dev macro-F1로 epoch를 선택하고 test는 variant·stage별 한 번만 평가
- class imbalance: inverse-frequency capped, 최대 비율 256

10 GiB cache를 매 epoch 다시 읽는 병목을 없애기 위해 모든 variant에 동일하게 `immutable FP32 disk cache → FP16 host memory → FP32 CUDA input` 전송을 적용했다. Smoke 비교에서 routing 출력은 일치했고 token score 차이는 약 `1.8e-5` 수준이었다. 이는 저장 표현 변경이 아니라 학습 중 전송 최적화다.

## 결과

### Shared sentence routing

| 표현 | best epoch | dev macro-F1 | test macro-F1 | test accuracy | legacy 대비 |
|---|---:|---:|---:|---:|---:|
| legacy L12 | 7 | 0.9081 | **0.8777** | 0.8902 | — |
| KF L10 | 5 | 0.8198 | 0.8191 | 0.8343 | -0.0586 |
| KF L12 | 5 | 0.7713 | 0.7478 | 0.7749 | -0.1299 |

이 결과는 “DeBERTa가 문장 표현에 약하다”는 뜻이 아니다. 현재 legacy 구조가 sentence routing에 맞게 형성되어 있고, KF에서는 특히 마지막 층보다 L10이 낫다는 뜻이다. routing 전용 scalar mix, attention pooling, loss/label routing을 비교해야 한다.

### 핵심 token/span Head

아래 값은 해당 Head의 token 또는 candidate 분류 macro-F1이다.

| 표현 | entity | time | semantic | trigger | 4-task 평균 |
|---|---:|---:|---:|---:|---:|
| legacy L12 | 0.3167 | 0.4259 | 0.6934 | 0.7622 | 0.5496 |
| KF L10 | **0.7074** | **0.8906** | **0.7646** | 0.9415 | **0.8260** |
| KF L12 | 0.7036 | 0.8783 | 0.7586 | **0.9512** | 0.8229 |

L10과 L12의 평균 차이는 `0.0031`뿐이므로 단일 seed에서 “L10 승리”로 일반화하면 안 된다. 더 중요한 사실은 task별 선호 층이 다르다는 점이다.

### Exact character-span

BIO는 argmax 후 잘못 시작된 `I`를 `B`로 처리했다. Boundary Head는 `sigmoid >= 0.5`, confidence 순 one-to-one start/end matching, 최대 폭 64, label·문장당 최대 4개로 복원했다. 이 decoder는 세 표현의 경계 품질을 같은 규칙으로 보는 진단용이며 최종 decoder 계약은 아니다.

| task | metric | legacy L12 | KF L10 | KF L12 | 현재 우세 |
|---|---|---:|---:|---:|---|
| entity | micro / macro F1 | 0.2557 / 0.2065 | 0.5577 / 0.4179 | **0.6243 / 0.5032** | L12 |
| time | micro / macro F1 | 0.1361 / 0.1383 | **0.8613** / 0.7208 | 0.8212 / **0.7271** | 혼합 |
| semantic | micro / macro F1 | 0.4586 / 0.4548 | **0.5273 / 0.5254** | 0.5044 / 0.4997 | L10 |
| trigger | micro / macro F1 | 0.6331 / 0.6331 | **0.8918 / 0.8918** | 0.8880 / 0.8880 | L10 근소 |

Entity는 KF L12가 L10보다 false positive를 줄여 micro-F1이 `+0.0666` 높았다. Time은 L10 micro-F1이 `+0.0401` 높고 L12 macro-F1이 `+0.0063` 높았다. 따라서 layer adapter를 task family 또는 label별로 학습할 근거가 있다.

## 실제 출력 비교

Test 기사 `GNEWS-31ea84d655fc870d54b5fea8764a606d`에서 end-exclusive character offset을 원문으로 복원했다.

### Entity와 time

| task | Gold | legacy L12 | KF L10 | KF L12 |
|---|---|---|---|---|
| entity | `대만`, `대만` | 정답 2개 + `국내` 2개 + `식`, `식약` | 정답 2개 + `싱가포르` | 정답 2개 + `남생활` |
| time | `2010년` | `2010년부터`, `2`, `56`, `2`, `8` | `2010년`, `일` | `2010년` |

KF는 같은 Head 계열을 다시 학습했을 뿐인데 legacy의 부분 단어와 숫자 과검출을 크게 줄였다. 다만 `싱가포르`처럼 언어적으로 타당해 보이지만 Gold에 없는 출력도 exact 평가에서는 false positive다. Gold의 exhaustive annotation 정책과 hard-negative 품질도 다음 단계에서 함께 감사해야 한다.

### Event trigger

Gold:

```text
드러났다 | 조치한다 | 검사했다 | 개였다 | 명령했으며 | 설명했다
```

legacy L12:

```text
드러났다 | 검사했다 |
검출된 화장품은 ... 등 2개였다 |
명령했으며, 온라인 플랫폼사에 해당 제품의 판매 중단도 요청했다 |
요청했다”고 설명했다
```

KF L10/L12:

```text
드러났다 | 조치한다 | 검사했다 | 개였다 | 명령했으며 | 요청했다 | 설명했다
```

두 KF 층은 Gold trigger 6개를 모두 포함하고 `요청했다` 하나를 추가했다. 반면 legacy는 trigger boundary를 긴 구절로 확장했다. DeBERTa 표현이 현재의 independent boundary Head에서도 한국어 술어 경계를 훨씬 선명하게 만든 사례다.

### EVENT/STATEMENT

Gold의 다음 STATEMENT에 대해:

```text
이에 따라 식약처는 ... 해당 제품의 판매중단을 요청했다.
```

- legacy L12는 동일 범위를 `EVENT`로만 예측했다.
- KF L10은 문장 후반부를 `EVENT`로 잡아 전체 STATEMENT 경계를 놓쳤다.
- KF L12는 동일 전체 범위를 `EVENT`와 `STATEMENT` 양쪽으로 예측했다.

즉 KF 표현만으로 `EVENT/STATEMENT` routing 문제가 사라지지는 않는다. span 중복·classification 불일치를 `MIX/AMBIGUOUS`로 다루는 consistency router가 필요하다는 기존 GLiNER 실험의 교훈과 일치한다.

## 해석과 설계 결정

### 확인된 사실

- KF-specific cache와 새 Head 학습은 핵심 token/span 성능을 크게 바꿨다.
- L10/L12의 유리한 task가 다르다.
- 기존 sentence routing 구조에서는 legacy L12가 여전히 우세하다.
- 동일 Head 구조에서도 KF가 entity/time/trigger의 exact boundary를 크게 개선했다.

### 추론

이전 probe의 낮은 KF 성능은 주로 “legacy 출력 공간에 KF 표현을 선형으로 끼워 넣은 평가”의 한계였다. 한국어 KF 표현 자체가 LocalKG supervision에 부적합하다는 증거가 아니었다. 반대로 이번 결과도 KF가 graph reasoning까지 해결했다는 증거는 아니다.

### 채택할 방향

`ArticleLocal-KG-DeBERTa`는 다음 구조를 첫 설계 기준으로 삼는다.

```text
KF-DeBERTa hidden states
        ↓
task-aware layer adapter / learned mix
        ├─ routing representation
        ├─ token/span representation
        └─ pair/coreference representation
        ↓
shared document context (selection은 prior, hard gate 아님)
        ├─ GLiNER-inspired label-conditioned span scorer
        ├─ directed pair scorer: assertor/argument/relation candidate
        └─ symmetric pair scorer: entity/event coreference
        ↓
consistency routing → deterministic offset/provenance → LocalKG materialization
```

기존 `ArticleLocal-KG`에서 가져올 것은 Gold/offset/cache/evaluation 계약과 graph task의 실패 경험이다. `ArticleLocal-KG-GLiner`에서 가져올 것은 label-conditioned span/schema 아이디어, native structured output를 시험한 경험, hard gate 제거, mention edge와 cluster edge의 분리다. 두 프로젝트의 runtime이나 checkpoint를 새 프로젝트에서 직접 import하지 않는다.

## 한계와 다음 실험

1. 단일 seed 결과다. L10/L12의 작은 차이는 3-seed 재현 전 확정하지 않는다.
2. backbone은 frozen이다. partial/full fine-tuning 결과는 아직 모른다.
3. 34개 기사는 tokenizer-boundary 정렬 때문에 token 비교에서 제외됐다. 정렬 정책을 수정하기 전 결과의 모집단은 966개다.
4. semantic span exact decoder는 임시 규칙이며 겹침·MIX를 충분히 표현하지 않는다.
5. epoch 상한 24에서 legacy와 KF L12 token stage가 최고 dev를 기록했다. 완전 수렴했다고 단정할 수 없다.
6. candidate/pair/coreference/relation과 end-to-end graph F1은 평가하지 않았다.

다음 순서는 다음과 같다.

1. KF L8/L10/L12 learned scalar mix를 routing과 token/span에 각각 평가한다.
2. 동일 Gold로 fixed Head와 label-conditioned span scorer를 비교한다.
3. Gold mention을 고정한 directed pair/symmetric coreference probe로 graph 계열 layer를 결정한다.
4. 이 세 gate가 통과한 뒤에만 새 프로젝트의 production Head inventory를 고정한다.

## 재현

```powershell
DirectionTest\.venv\Scripts\python.exe DirectionTest\build_kf_layer_caches.py --layers 10 12 --device cuda
DirectionTest\.venv\Scripts\python.exe DirectionTest\train_kf_layer_head_ablation.py --variants legacy_l12 kf_l10 kf_l12 --device cuda --output DirectionTest\artifacts\kf-layer-head-ablation-v2
```

재현 스크립트:

- 실험 당시 `build_kf_layer_caches.py` SHA-256 `16706640d4ce147d4444203d0b6124f53d7b4925610bf457fa9153256ada2232`
- `train_kf_layer_head_ablation.py` SHA-256 `6fbae873996f333d50ce9e573ad275f7f19c7fd7fc81e3db7661ef7502111ce7`
- `summary.json` SHA-256 `e73b32980c2f2e942af1c6e74a44b0f472c8de8b0f9c570d6f2be5cb9e53417b`

후속 L8 probe에서 같은 cache 계약을 유지하면서 결과 파일 덮어쓰기를 막기 위한 `--summary-name` 옵션만 추가했다. 현재 build script 해시는 달라졌지만 이 L10/L12 실행 결과의 code provenance는 위 당시 해시로 고정한다.

Cache 생성은 617.5초, 세 variant 재학습·평가는 총 3,097.8초(약 51.6분) 걸렸다. Variant별 peak allocated CUDA memory는 약 1.12 GiB였다.
