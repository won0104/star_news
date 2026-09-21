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
