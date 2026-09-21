# 9번 Assertor·semantic relation 계약

## 확인한 입력과 범위

- r05.3 compiler의 `assertor_source`는 Statement별 exact source 또는 없음이다. `assertor_entity`는 resolved Statement×Gold EntityCluster, `about`은 Statement×Gold EventCluster, `causes`는 ordered distinct Gold EventCluster×Gold EventCluster의 closed-world universe다.
- 6번 Entity union은 `ASSERTOR` origin과 `SPAN_ONLY`를 지원했고, 8번 final Event feature lease는 `RELATION`과 `PRIMARY`가 마지막 소비자까지 공유하도록 이미 예약돼 있었다.
- 기존 `models/pairs/assertor.py`는 이미 제공된 pair state의 선형 분류기다. 과거 source-first 실험은 source candidate recall 1.0에도 predicted exact source F1 0.0223, resolved edge precision 0.0282로 runtime promotion이 차단되었다. 그 실험의 curated `UNKNOWN` supervision과 가중치는 r05.3 head로 가져오지 않았다.

## 실행 경로

검증된 train Gold adapter는 한 backbone·공유 DCE·direct gather로 Statement, Assertor, Event, role, Entity, Time 표현을 준비한다. Statement-conditioned Assertor head는 source 존재 여부, source token start/end, exact signed character residual 및 source span 적합도를 학습한다. Gold의 source 없는 Statement는 존재 여부의 음성이고, 존재하는 source는 exact boundary 감독이다. 이 감독은 Entity NER 후보에 의존하지 않는다.

resolved Assertor 근거는 같은 article-local Entity union·typing·coreference·resolution으로 들어간다. 학습에서 Gold Entity ID는 label을 final local ID에 대응하는 데만 쓰며 모델 입력에는 넣지 않는다. `entity_id=null`의 textual source는 `SPAN_ONLY`로 남고 Entity node/ASSERTED_BY edge를 만들지 않는다. predicted 경로도 source가 선택된 뒤 Entity 후보와 병합하고 별도 Assertor→Entity head의 잠정 logit 정책으로 endpoint를 결정한다. 기각된 Assertor-only 후보는 최종 Entity closure에서 제거한다.

ABOUT은 `Statement → final EventCluster`, CAUSES는 `final EventCluster → final EventCluster`이며 두 독립 directed adapter를 쓴다. 학습은 compiler의 양성 및 같은 universe에서 재현 가능하게 뽑은 음성만 평가한다. CAUSES의 역방향은 독립 eligible pair이고 self pair는 없다. runtime은 Gold ID 없이 final local ID와 Statement local ID만 사용한다. Pair scoring은 chunk와 budget으로 제한하고 초과분을 partial로 보고한다. scalar fact만 semantic carrier로 이동한다.

## 소비자와 비용

관계 loss와 runtime scorer는 final lease의 `RELATION` view를 소비한다. caller가 이후 `release("RELATION")`을 호출하더라도 `PRIMARY`가 남아 있으므로 tensor는 유지된다. training loss가 autograd graph를 보유한 채 두 consumer를 release한 후 backward할 수 있다. `LocalEventState`에는 raw tensor를 보관하지 않는다. 모델 head는 256 차원의 작은 MLP 네 개이고 backbone/DCE 재실행은 없다. 후보 pair 전체의 `[S,C,H]` 또는 `[C,C,H]` tensor를 만들지 않는다.

## 검증과 제한

400개 verified 기존 train Gold의 Assertor source 3,347개, 그중 SPAN_ONLY 315개, resolved ASSERTED_BY 3,032개, ABOUT 1,772개, CAUSES 615개가 source/identity 정적 검사를 통과했다. engineering50도 별도 집계했다. synthetic backbone을 쓴 실제 train Gold의 네 loss가 finite이고 각 head의 gradient가 0이 아님을 확인했다. predicted path에서 source 복원, Entity resolved/기각, local ID ABOUT/방향 CAUSES와 lease release를 확인했다.

`score_threshold=0`, `assertor_resolution_threshold=0`, pair budget은 engineering 기본값이며 service cutoff가 아니다. 이전 실험에서 드러난 source 경쟁 후보의 품질 문제는 새 weight를 본학습하기 전까지 해소되었다고 주장하지 않는다. 전체 Gold intake는 기존 dev Gold 136의 Time schema 문제로 BLOCKED 상태다. dev/test는 이 단계의 구현 검증과 설정 선택에 사용하지 않았다.
