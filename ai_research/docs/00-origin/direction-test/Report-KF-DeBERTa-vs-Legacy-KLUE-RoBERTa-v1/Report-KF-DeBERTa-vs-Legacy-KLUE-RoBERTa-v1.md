# KF-DeBERTa vs legacy KLUE-RoBERTa CUDA 방향성 실험

- 실험일: 2026-09-02
- 실험 ID: `kf-deberta-vs-legacy-v1`
- 상태: 완료
- 대상: `ArticleLocal-KG`의 현재 로컬 KLUE-RoBERTa 계열 encoder와 `kakaobank/kf-deberta-base`
- 제품 코드 변경: 없음

## 결론

`kakaobank/kf-deberta-base`를 현재 encoder 자리에 바로 교체할 근거는 이번 실험에서 나오지 않았다.

같은 Gold v2.0, 같은 article split, 같은 frozen linear probe 조건에서 KF-DeBERTa의 test macro-F1은 `0.5032`였고 현재 로컬 KLUE-RoBERTa encoder는 `0.5931`이었다. KF-DeBERTa가 `0.0899`, 즉 약 `9.0%p` 낮았다. Accuracy도 `0.6451` 대 `0.7543`으로 낮았다.

반면 두 가지 장점은 확인됐다.

1. KF-DeBERTa tokenizer가 문장을 더 짧게 표현했고 `[UNK]`와 truncation이 적었다.
2. KF-DeBERTa의 후반층은 현재 RoBERTa보다 token representation의 유효 rank가 높고 token끼리 덜 붕괴되어 있었다.

따라서 이번 결과는 **KF-DeBERTa 기각**이 아니라 **무조건적인 backbone 교체 보류**로 판정한다. 다음 비교는 frozen 출력이 아니라 동일한 LocalKG head를 붙인 matched fine-tuning이어야 한다. GLiNER checkpoint를 채택하는 것보다 GLiNER의 label-conditioned span/pair scoring 아이디어를 backbone과 분리해 시험하는 쪽이 현재 증거와 더 잘 맞는다.

## 무엇을 비교했는가

Transformer의 hidden state 자체는 사람이 읽을 수 있는 자연어 출력이 아니다. 그래서 이번에는 출력을 세 방식으로 비교했다.

1. 모든 layer의 `CLS`와 mean-pooled hidden state에 동일한 `768 → 2` linear probe를 붙여 `EVENT`와 `STATEMENT` 확률을 출력했다.
2. token cosine과 effective rank로 층별 representation geometry를 비교했다.
3. 사람이 읽을 수 있는 보조 출력으로 동일한 한국어 문장에 대한 MLM top-5를 비교했다.

여기서 1번이 LocalKG 방향성 판단의 주 지표이고, 2번은 “DeBERTa가 더 다양한 층별 출력을 주는가”에 대한 진단 지표다. 3번 MLM은 출력 감각을 보기 위한 예시일 뿐 LocalKG 성능 지표가 아니다.

## 재현 환경

| 항목 | 값 |
|---|---|
| OS | Windows |
| Python | 3.12.13 |
| PyTorch | `2.11.0+cu128` |
| CUDA runtime | 12.8 |
| GPU | NVIDIA GeForce RTX 4050 Laptop GPU |
| Compute capability | 8.9 |
| Transformers | 4.57.6 |
| 실행 환경 | `DirectionTest/.venv` |

CUDA smoke test에서 `torch.cuda.is_available() == True`를 확인했고 FP16 `2048 × 2048` matmul을 통과했다. `pip check`도 broken requirement 없이 통과했다.

기존 `ArticleLocal-KG-GLiner/.venv`는 CPU 환경 그대로 두었다. 이번 CUDA 환경은 `DirectionTest`에 격리했으며 `ArticleLocal-KG`와 기존 checkpoint를 수정하지 않았다.

## 모델 고정값과 provenance

| 항목 | 현재 legacy 측 | 후보 측 |
|---|---|---|
| 표시명 | ArticleLocal-KG legacy KLUE-RoBERTa encoder | `kakaobank/kf-deberta-base` |
| representation source | 로컬 `ArticleLocal-KG/model/LQ-FSE/model_artifacts/huggingface/lq-fse-base` | Hugging Face |
| revision | `1e86ec3ce0f2670966bfe3875eb5cd1805c800ac` | `363b171d71443b0874b0bf9cea053eb5b1650633` |
| model type | RoBERTa | DeBERTa-v2 |
| hidden/layers/heads | 768 / 12 / 12 | 768 / 12 / 12 |
| FFN intermediate | 3072 | 3072 |
| vocab | 32,000 | 130,000 |
| position | absolute position embedding | relative attention, `p2c + c2p`, `position_biased_input=false` |

Legacy 측은 공식 `klue/roberta-base`를 다시 받은 것이 아니라 실제 프로젝트의 로컬 LQ-FSE encoder를 사용했다. checkpoint의 `sentence_encoder.*` tensor 199개를 `RobertaModel`에 strict-load했고 missing/unexpected key가 없음을 확인했다.

- 로컬 checkpoint SHA-256: `fe1ffbfc8dfaecea427d0058ae2bb97ee3ada124d53d1e2db5cdf11b202f999d`
- [KF-DeBERTa 공식 모델 카드](https://huggingface.co/kakaobank/kf-deberta-base)
- [KLUE-RoBERTa 공식 모델 카드](https://huggingface.co/klue/roberta-base)

KF-DeBERTa 공식 모델 카드는 범용·금융 말뭉치를 함께 학습했고, task fine-tuning을 거친 KLUE/금융 benchmark에서 강한 결과를 보고한다. 따라서 이번 frozen probe의 열세와 공식 benchmark 결과는 모순이 아니다. 이 프로젝트에 맞춘 fine-tuning 전에는 실제 적응 폭을 알 수 없다.

## 데이터와 평가 계약

| 항목 | 값 |
|---|---|
| processed data | `gnews-1k-v1.0.json` |
| Gold | `gnews-1k-construction-gold-v2.0.json` |
| 기사 | 1,000 |
| 문장 | 27,403 |
| state 분포 | EVENT 7,650 / STATEMENT 11,869 / MIX 168 / DROP 7,716 |
| split | 기사 단위 800 / 100 / 100 |
| seed | 41 |
| test 문장 | 2,499 |
| max length | 128 |
| backbone | frozen |
| 후보 feature | embedding + encoder 12개 층, 각 `CLS`/mean pooling |
| probe | pooling×layer마다 독립적인 `768 → 2` linear layer |
| loss | train-only positive-weighted EVENT/STATEMENT BCE |
| epoch | 40 |
| routing | 두 확률을 0.5에서 threshold해 EVENT/STATEMENT/MIX/DROP |
| selection | dev에서 pooling/layer/epoch 선택 후 test 1회 평가 |

Gold semantic span이 한 문장 안에 완전히 포함되는지를 기준으로 EVENT/STATEMENT bit를 만들었다. 이 실험은 기존 16-head 전체나 최종 LocalKG graph를 재현한 것이 아니라, backbone representation의 방향성을 빠르게 비교하기 위한 중립적인 sentence-only probe다.

## 결과 1: downstream 방향성 probe

| 지표 | legacy KLUE-RoBERTa | KF-DeBERTa | KF - legacy |
|---|---:|---:|---:|
| 선택 pooling/layer | CLS / L12 | mean / L10 | - |
| dev macro-F1 | 0.5946 | 0.5338 | -0.0608 |
| test macro-F1 | **0.5931** | 0.5032 | **-0.0899** |
| test accuracy | **0.7543** | 0.6451 | **-0.1092** |
| EVENT F1 | **0.7643** | 0.6729 | -0.0914 |
| STATEMENT F1 | **0.8051** | 0.7054 | -0.0997 |
| MIX F1 | **0.0503** | 0.0392 | -0.0111 |
| DROP F1 | **0.7528** | 0.5954 | -0.1574 |

MIX test support는 22문장뿐이고 두 모델 모두 MIX를 과다 예측했다. MIX 절대값은 안정적인 모델 순위 지표로 해석하면 안 된다. 핵심은 표본이 충분한 EVENT, STATEMENT, DROP에서도 이번 조건의 KF-DeBERTa가 모두 낮았다는 점이다.

공식 모델 카드의 fine-tuned KLUE benchmark와 달리 이 실험은 backbone을 얼린 선형 분리도 비교다. 따라서 여기서 말할 수 있는 것은 “현재 Gold에 대한 zero-adaptation feature separability는 legacy가 낫다”까지다.

## 결과 2: 모든 층의 dev macro-F1

각 값은 해당 pooling/layer의 독립 probe가 dev에서 낸 최선의 macro-F1이다.

| Layer | legacy CLS | legacy mean | KF CLS | KF mean |
|---:|---:|---:|---:|---:|
| Embedding L0 | 0.150 | 0.462 | 0.150 | 0.475 |
| L1 | 0.406 | 0.468 | 0.426 | 0.477 |
| L2 | 0.434 | 0.483 | 0.440 | 0.493 |
| L3 | 0.461 | 0.509 | 0.457 | 0.511 |
| L4 | 0.474 | 0.514 | 0.475 | 0.515 |
| L5 | 0.485 | 0.521 | 0.486 | 0.519 |
| L6 | 0.457 | 0.539 | 0.441 | 0.517 |
| L7 | 0.463 | 0.559 | 0.418 | 0.524 |
| L8 | 0.472 | 0.563 | 0.415 | 0.522 |
| L9 | 0.515 | 0.574 | 0.367 | 0.534 |
| L10 | 0.549 | 0.582 | 0.414 | **0.534** |
| L11 | 0.582 | **0.594** | 0.395 | 0.528 |
| L12 | **0.595** | 0.593 | 0.485 | 0.515 |

관찰 사항:

- Legacy는 후반으로 갈수록 거의 단조롭게 좋아지고, L11~L12에서 CLS와 mean이 모두 강하다.
- KF-DeBERTa는 mean pooling이 일관되게 CLS보다 낫고 L9~L10에서 최고점에 도달한 뒤 낮아진다.
- 따라서 KF-DeBERTa를 쓴다면 무조건 마지막 `CLS`만 사용하는 adapter는 부적절할 가능성이 높다.
- span/token task와 pair/document task가 서로 다른 layer를 요구할 수 있으므로, 후보 구현은 L6~L12 scalar mix 또는 task별 layer selection을 ablation해야 한다.

## 결과 3: “더 다양한 출력” 가설

여기서 representation 다양성은 **한 문장 안 token hidden state의 평균 off-diagonal cosine이 낮고, singular value 기반 effective rank가 높은 상태**로 정의했다. 의미 범주의 다양성이나 최종 예측 정확도를 뜻하지 않는다.

| Layer | legacy token cosine | KF token cosine | legacy effective rank | KF effective rank |
|---:|---:|---:|---:|---:|
| L0 | 0.054 | **0.042** | **29.73** | 28.15 |
| L3 | **0.140** | 0.263 | **27.78** | 26.11 |
| L6 | **0.196** | 0.325 | 23.76 | **24.48** |
| L9 | **0.386** | 0.424 | 18.99 | **24.20** |
| L10 | **0.465** | 0.550 | 17.61 | **24.22** |
| L12 | 0.971 | **0.596** | 11.52 | **26.04** |

최종층에서는 가설이 뚜렷하게 맞았다. Legacy L12는 token cosine `0.971`, effective rank `11.52`로 token representation이 강하게 모였지만 KF L12는 `0.596`, `26.04`였다. KF의 L11→L12 CLS cosine도 `0.197`이라 최종층에서 큰 표현 변환이 있었다. Legacy의 같은 값은 `0.524`였다.

그러나 더 높은 effective rank가 자동으로 task-relevant separation을 만들지는 않았다. KF의 best layer는 마지막층이 아닌 mean L10이었고, 그 점수도 legacy보다 낮았다. 즉 “다양하다”와 “현재 LocalKG label에 선형 분리 가능하다”를 분리해서 봐야 한다.

## 결과 4: tokenization

| 지표 | legacy tokenizer | KF tokenizer |
|---|---:|---:|
| 평균 token 수 | 35.93 | **33.44** |
| p50 | 32 | **30** |
| p95 | 72 | **66** |
| 원문 최대 token 수 | 495 | **392** |
| max length 128에서 truncation | 69 | **50** |
| `[UNK]` / source token | 1,751 / 925,888 | **1,187 / 858,941** |
| `[UNK]` 비율 | 0.189% | **0.138%** |

예시 1:

```text
입력: 추 위원장은 “판결문을 읽으며 눈물이 났다”며 “이것이야말로 국민의 마음”이라고 했다.

legacy 일부: 이것 / ##이 / ##야 / ##말로 ... 이라 / ##고 / 했 / ##다
KF 일부:     이것 / ##이야 / ##말로 ... 이라고 / 했다
전체 길이: legacy 30, KF 27 (special token 포함)
```

예시 2:

```text
입력 일부: ... “OLX301A는 시력 기능 보존과 개선 가능성까지 ...”

legacy: O / ##L / ##X / ##30 / ##1 / ##A ... 가능 / ##성 / ##까 / ##지
KF:     OLX / ##30 / ##1 / ##A ... 가능 / ##성 / ##까지
전체 길이: legacy 72, KF 66 (special token 포함)
```

KF의 130k vocab이 뉴스·금융 표현을 더 덩어리 있게 잡는 경향은 확인됐다. 다만 vocab 증가에 따른 embedding memory 비용도 있다.

## 결과 5: 사람이 읽을 수 있는 MLM 출력

Legacy 로컬 LQ-FSE package에는 MLM head가 없으므로 이 절만 공식 `klue/roberta-base` MLM head를 사용했다. 따라서 아래 표는 **두 pretrained language model의 단어 완성 예시**이지, 위 probe에서 쓴 실제 legacy representation의 head-to-head 출력은 아니다.

| 입력 | KLUE-RoBERTa top-5 | KF-DeBERTa top-5 |
|---|---|---|
| 삼성전자는 올해 반도체 투자를 `[MASK]`할 계획이다. | 확대 0.285, 마무리 0.100, 더 0.087, 꾸준히 0.073, 계속 0.069 | 확대 0.186, 본격화 0.140, 두배로 0.104, 꾸준 0.098, 계속 0.062 |
| 한국은행은 기준금리를 3.5%로 `[MASK]`했다. | 동결 0.553, 유지 0.123, 인하 0.118, 인상 0.060, 결정 0.014 | 동결 0.757, 유지 0.041, 인상 0.038, 인하 0.035, 올린다고 0.031 |
| 집중호우로 도로가 `[MASK]`됐다. | 침수 0.690, 파손 0.053, 유실 0.042, 통제 0.035, `[PAD]` 0.022 | 침수 0.439, 파손 0.087, 마비 0.073, 물바다 0.050, 유실 0.048 |

두 모델 모두 세 문장의 1순위를 자연스럽게 맞혔다. KF는 기준금리 문장에서 `동결`에 더 집중했고, 다른 두 문장에서는 top 후보 확률을 더 넓게 분산했다. 세 문장만으로 언어 능력의 우열을 판정할 수는 없다.

KF MLM model load 시 `deberta.embeddings.position_embeddings.weight`가 사용되지 않았다는 Transformers 경고가 있었다. 이 checkpoint config가 `position_biased_input=false`, relative attention을 사용하기 때문인 것으로 해석된다. representation probe의 encoder load와 실행은 정상 완료됐다.

## 결과 6: 실제 EVENT/STATEMENT 출력

아래 확률은 dev에서 선택된 legacy `CLS L12`와 KF `mean L10` probe의 test 문장 출력이다. 같은 threshold 0.5를 적용했다.

### EVENT 예시

```text
Gold: EVENT
입력: 현재는 안중근의사기념관에 기증한 상태다.
legacy: EVENT=0.8968, STATEMENT=0.0858 → EVENT
KF:     EVENT=0.9924, STATEMENT=0.0171 → EVENT
```

```text
Gold: EVENT
입력: 추 위원장은 “판결문을 읽으며 눈물이 났다”며 “이것이야말로 국민의 마음”이라고 했다.
legacy: EVENT=0.5154, STATEMENT=0.2711 → EVENT
KF:     EVENT=0.5658, STATEMENT=0.2831 → EVENT
```

### STATEMENT 예시

```text
Gold: STATEMENT
입력: 이 대표는 “현재 치료제는 질환 진행 억제 자체에는 의미가 있지만, 환자 입장에서는 결국 ‘잘 보이느냐’가 가장 중요하다”며 “OLX301A는 시력 기능 보존과 개선 가능성까지 겨냥하고 있다는 점에서 접근 방식이 다르다”고 설명했다.
legacy: EVENT=0.0151, STATEMENT=0.9985 → STATEMENT
KF:     EVENT=0.1163, STATEMENT=0.8792 → STATEMENT
```

### MIX 예시

```text
Gold: MIX
입력: 이어 “주변에 있는 미디어센터에는 내외신 언론인뿐만 아니라 대표단 등 에이펙 참가자 전부가 이용할 수 있다”고 설명했다.
legacy: EVENT=0.7069, STATEMENT=0.6967 → MIX
KF:     EVENT=0.6058, STATEMENT=0.7607 → MIX
```

```text
Gold: MIX
입력: 이는 도널드 트럼프 미국 대통령이 베네수엘라 제재를 강화하면서 지리적 긴장이 고조된 점도 금 가격 상승을 부추긴 것으로 보인다.
legacy: EVENT=0.1368, STATEMENT=0.2411 → DROP
KF:     EVENT=0.5605, STATEMENT=0.1735 → EVENT
```

### DROP 예시

```text
Gold: DROP
입력: 이와 관련해 A씨는 "3차 병원에서 진단받은 결과만 유효하고 1차 병원에서 받은 부정맥 진단은 지급 근거로 활용할 수 없다는 것인데, 도대체 약관 어디에 그러한 내용이 있는지 묻고 싶다"고 지적했다.
legacy: EVENT=0.0292, STATEMENT=0.0811 → DROP
KF:     EVENT=0.1948, STATEMENT=0.2407 → DROP
```

확률 보정은 하지 않았다. 이 값은 후보 score이며 최종 graph 판정값으로 사용하면 안 된다.

## 자원 사용

| 항목 | legacy | KF-DeBERTa |
|---|---:|---:|
| peak CUDA memory | 709.8 MiB | 973.2 MiB |
| 모델별 전체 단계 시간 | 183.0 s | 432.7 s |
| tokenization 시간 | 51.2 s | 90.2 s |

동일 batch size 48에서 KF가 약 263 MiB 더 사용했다. 큰 vocab embedding의 영향이 포함된다. 시간은 모델 download를 제외한 해당 모델의 tokenization, hidden-state 추출, probe, 진단 출력 단계를 합친 방향성 수치다. 정식 latency benchmark는 아니다.

## 판정과 다음 실행 순서

### 판정

1. 현재 legacy checkpoint를 baseline으로 보존한다.
2. `kf-deberta-base`를 즉시 default backbone으로 바꾸지 않는다.
3. 그렇다고 KF를 제외하지도 않는다. compact tokenization과 후반층 representation rank는 span/pair architecture에서 재평가할 가치가 있다.
4. GLiNER는 checkpoint 채택보다 label-conditioned span/schema와 candidate pair 생성 아이디어를 가져오는 쪽을 우선한다.

### 다음 실험 순서

1. `ArticleLocal-KG`에 runtime 기본값을 바꾸지 않는 pluggable backbone adapter를 설계한다.
2. 동일한 개선형 span/pair head를 legacy와 KF에 각각 붙인다. head parameter count, optimizer, article split, max length, update step을 맞춘다.
3. 각 backbone을 frozen이 아닌 full fine-tuning 또는 동일한 PEFT 조건으로 3 seeds 비교한다.
4. backbone별로 `last layer`, `best single layer`, `learned scalar mix`를 ablation한다. KF는 우선 L6~L12 mean/token representation을 후보로 둔다.
5. ENTITY/TIME/EVENT/STATEMENT/TRIGGER exact span F1부터 통과시킨 뒤 argument/relation candidate recall과 coreference를 평가한다.
6. 마지막에만 article-to-LocalKG graph F1과 latency/memory로 default backbone을 결정한다.

권장 architecture는 다음 책임 분리다.

```text
Korean backbone (legacy KLUE-RoBERTa | KF-DeBERTa)
  → task-aware layer mix
  → GLiNER-inspired label-conditioned span scorer
  → directed pair scorer (assertor / argument / relation)
  → symmetric pair scorer (entity/event coreference)
  → deterministic evidence / graph validation
```

이 순서라면 “KF의 pretrained weight가 좋은가”와 “GLiNER식 구조가 좋은가”를 같은 실험에서 섞지 않고 각각 검증할 수 있다.

## 한계

- single seed다.
- sentence-only frozen linear probe다.
- Gold v2.0은 완전히 독립적인 blind human benchmark가 아니다.
- document context, span boundary, argument, relation, coreference, 최종 graph를 평가하지 않았다.
- legacy 측의 사람이 읽을 수 있는 MLM 출력만 공식 KLUE MLM head를 사용했다.
- class imbalance가 매우 크며 특히 MIX 표본이 적다.

따라서 `9.0%p` 차이를 최종 fine-tuned 성능 차이로 외삽하면 안 된다. 이번 실험의 역할은 비싼 전면 교체 전에 후보의 출력 성질과 zero-adaptation separability를 확인하는 것이다.

## 재현

실행 스크립트:

```powershell
DirectionTest\.venv\Scripts\python.exe DirectionTest\kf_deberta_vs_legacy_probe.py
```

machine-readable 결과:

```text
DirectionTest/artifacts/kf-deberta-vs-legacy-v1.json
```

재현 가능한 model cache, virtual environment, JSON artifact는 Git에서 제외했고, 실험 계약과 사람이 읽을 판정은 이 보고서와 실행 스크립트에 남겼다.

검증 완료 항목:

- CUDA availability 및 FP16 matmul
- local legacy encoder 199 tensor strict-load
- 두 모델 27,403문장 hidden-state 추출
- 모든 pooling/layer 독립 probe 학습
- dev selection 후 test 단회 평가
- MLM 및 representative output 생성
- JSON artifact 생성
- `pip check`
