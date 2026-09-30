# 단계 3: r05.3 target·음성 universe 계약

## 입력과 정렬

`ValidatedGoldArticle`은 단계 2 source join의 `PASS` 및 기존 train 소속만 허용한다. `RawArticle`과 `SourceLayout`은 Gold 필드가 없는 runtime 입력이다. compiler는 `ValidatedGoldArticle`을 요구하며 raw 입력을 거부한다. 이전 Gold380·annotation label, 기사 순번·ID, annotator confidence/rationale, 5–8개 quota를 모델 feature/label로 쓰지 않는다. 내부 Gold ID는 같은 기사 target을 결합하는 키일 뿐이다.

Pinned KF tokenizer revision `363b171d71443b0874b0bf9cea053eb5b1650633`와 tokenizer JSON SHA `915388090e2d63e3869c54b5334d6005e453a51de12088d908175dd765fd8372`를 검증한다. 기존 sentence splitter와 128-token sentence view를 보존하고, 동일한 원문에서 128-token bridge view(실제 source token 126개, stride 64)를 Gold 없이 결정한다. `article_version_id`·본문 SHA·tokenizer hash·layout policy·window ID는 캐시 일치성에 필요하며 feature가 아니다. 각 boundary는 token 위치와 부호 있는 문자 잔차를 기록한다. token 내부/공백 경계를 반올림하지 않으며, 긴 span은 양 끝의 서로 다른 window 참조를 보존한다. overlap의 동일 근거는 `(kind,start,end,label)` 절대 좌표로 닫고 다른 occurrence는 보존한다.

단계 3의 `unrepresentable=0`은 **compiler의 문자 좌표 계약** 안에서 target이 유실되지 않았다는 뜻이다. 기존 rc2 head나 아직 구현하지 않은 단계 5–10 head가 이 잔차·cross-window link를 학습할 수 있다는 뜻은 아니다. 실제 head별 지원과 gradient는 후속 단계에서 검증한다. source window는 request/stage lifetime에만 두고 PUBLIC 상태에 보관하지 않는다.

## task별 target과 mask

| task | 양성/label | 음성 또는 무시 |
|---|---|---|
| semantic proposer·boundary·validity | Event/Statement의 exact source span과 kind | 모든 미기록 span을 음성으로 만들지 않는다. 후보 기반 hard negative는 provenance가 확인된 별도 계약 전까지 미정이다. |
| Trigger | 각 Event의 exact trigger span | 미기록 임의 span은 자동 음성으로 만들지 않는다. |
| ACTOR/TARGET/PLACE | Event-conditioned exact filler span·role | Entity endpoint는 별도 resolution. PLACE `entity_id=null`의 span은 양성, resolution은 `IGNORE`. |
| EntityMention·priority | 5-type exact span; priority는 exact retained boundary에서 파생 | priority에 Primary rank를 쓰지 않는다. 임의 미기록 span은 자동 음성화하지 않는다. |
| TimeMention·normalization | generic exact span은 null이어도 양성; non-null normalization 값 감독 | normalized null은 normalization `IGNORE`이며 Time span/attachment 음성이 아니다. |
| StatementType·Assertor source | Statement type; 명시 Assertor span | Assertor null은 source/resolution `IGNORE`; span-only assertor는 source 양성·resolution `IGNORE`. |
| Entity/Event coreference | 같은 Gold cluster의 unordered distinct mention/Event 쌍 | 서로 다른 Gold cluster의 쌍. Event member마다 rank를 반복하지 않는다. |
| Role→Entity·Assertor→Entity | non-null endpoint 쌍 | 같은 기사 다른 Entity cluster 쌍. null endpoint는 pair universe에서 제외하고 별도 `IGNORE`로 집계한다. |
| Event→Time | 명시된 Event.times 쌍 | 같은 기사 나머지 Event×TimeMention 쌍. |
| ABOUT | 명시 Statement→EventCluster 쌍 | **완성 annotation으로 검증된 기사**의 나머지 Statement×EventCluster 쌍. |
| CAUSES | 명시 EventCluster→EventCluster 쌍 | 같은 기사의 나머지 순서 있는 서로 다른 EventCluster 쌍. 자기 edge 불가. |
| Primary | EventCluster∪Statement 사이 strict rank pair, 작은 rank 우선 | 같은 rank pair는 `TIE_IGNORE`; score 거리/확률 target이 아니다. |

`PairUniverse`는 전체 논리 universe를 lazy iterator로 유지한다. `sample_negatives(limit,seed,content_sha)`는 학습용 재현 표본만 만들며 평가의 eligible pair 집합을 바꾸지 않는다. predicted pair의 미평가 사례를 Gold 음성으로 바꾸지 않는다. ABOUT/CAUSES의 의미적 누락 여부는 기계 검사만으로 인증할 수 없어 단계 2 Gold 검증 상태를 상속한다.

## 평가 경계와 현재 범위

Exact matcher는 `GOLD_INJECTED`, `GOLD_SPAN`, `PREDICTED_SPAN` cohort를 결과에 필수로 붙인다. span/type·role·cluster pair·관계 방향쌍에는 exact key를 사용하고 Primary의 tie pair는 순서 정확도에서 제외한다. 이 단계는 모델 예측 품질이나 calibration을 측정하지 않았다.

`target-coverage-report.json`은 검증 통과한 기존 train Gold 400기사에 한정한다. dev/test Gold는 구현·tiny-fit·모델 선택에 사용하지 않았다. `gold_verified/136.json`의 dev Time 구간 오류로 전체 Gold intake는 여전히 `BLOCKED`이며, 전체 Gold가 통과한 것처럼 최종 학습 준비를 선언하지 않는다.

---

## 부록 A: span 음성의 "미정" 해제 (extraction repair v1)

위 본문은 단계 3 시점의 기록이며 span task의 음성을 **미정**으로 남겼다. 이 부록은 그 미정을 해제한 범위만 추가하고 본문 기록은 바꾸지 않는다. 상세 근거와 계측은 [extraction-repair-report.md](extraction-repair-report.md)에 있다.

### 완결성 전제의 적용 범위

r05.3 §1.4는 기사 전체 검토를 **전제로 선언**하지만, closed-world를 명시한 것은 `ABOUT`/`CAUSES`뿐이다. §5.1은 EntityMention을 "독립적으로 식별할 가치가 있는 referent"로 좁히고, §2.5는 반복 언급을 "각각 보존**할 수 있다**"는 허용형으로 둔다. `v3_gold_intake.validate_article`은 참조 무결성과 `content[start:end] == text`만 검사하며, `gold-validation.json`은 `semantic_relation_completeness = NOT_MECHANICALLY_CERTIFIED`, `status = BLOCKED`을 기록한다.

따라서 **schema/hash 검증 PASS는 annotation completeness의 증거가 아니다.** 아래 규칙은 완결성 전제를 요구하지 않는 근거만으로 성립하며, EVENT/STATEMENT의 일반적인 "미기록 = negative"는 여전히 적용하지 않는다.

### 승인된 음성 규칙과 책임

| 규칙 | 생성 | 적용 책임 | 전파 금지 |
|---|---|---|---|
| `N1_BOUNDARY_MISMATCH` | Gold span 양끝을 이웃 source-token 경계로 ±2 이동 | `EXACT_SPAN_FITNESS` | semantic validity, span 존재 |
| `N2_KIND_EXCLUSIVE` | 같은 좌표의 다른 proposition kind Gold (§2.1/§2.2) | 해당 kind `DETECTION` | span 존재 자체 |
| `N3_REPORTING_WRAPPER` | Gold STATEMENT + 뒤따르는 §4.2.3 carrier | EVENT `DETECTION` + `SEMANTIC_VALIDITY` | 다른 유효 proposition |
| `N4_TRIGGER_WITHOUT_EVENT` | Gold Event 없는 Statement 구간의 trigger 크기 span | TRIGGER `DETECTION` | EVENT/STATEMENT 존재 |

`SpanNegative.__post_init__`이 규칙별 책임을 강제하며, 책임을 넓혀 생성하면 예외로 실패한다. 규칙별 count는 `규칙:책임` 키로 분리해 보고하고 합산하지 않는다.

### IGNORE

`I1_REPEAT_OCCURRENCE`(§2.5 반복 언급), `I2_OVERLAPS_GOLD`, `I3_OMISSION_SUSPECTED`는 음성이 아니라 손실에서 제외한다. 근거가 조금이라도 불확실하면 음성보다 IGNORE를 우선한다.

### 적용 제외

- ENTITY/TIME에는 위 규칙을 확장하지 않는다. §5.1/§6.1의 annotation 범위가 다르다.
- `N4`는 기본 비활성(`TargetCompiler(enable_trigger_absence_negatives=False)`)이다. 승인 조건의 재진술 가드를 적용하면 비동사 파편만 남아 판별 가치가 없다는 것이 계측으로 확인됐다.
- 생성 endpoint logit(`exact_source_span.endpoint_logits`)과 task별 boundary logit은 확정 음성이 없으므로 **양성 전용으로 유지**한다. 판별 신호는 in-window joint proposal cell과 span score가 맡는다.
