# 8번 최종 Event identity·cluster 표현·owner 계약

## 동일성 경로

3번 compiler의 `event_coreference` universe는 서로 다른 EventMention 두 개가 **같은 실제 occurrence**인 경우만 양성이다. 인과·시간 선후·같은 주제·공유 Time/Entity는 단독 merge 규칙이 아니다. `EventGoldAdapter`는 검증된 기존 train Gold pair 전체 양성과 결정적 표본 음성을 fresh `event_coreference`의 대칭 CE에 연결한다. Gold cluster ID는 label 검사에만 사용한다. 예측 경로는 `score_event_identity`가 bounded/chunked pair score를 내고 `close_event_identity`가 complete-link로 최종 local ID를 만든다. 점수 없는 pair는 미평가이며 음성이 아니다. unaligned Event는 singleton과 partial 상태로 남는다. `strict_equivalence_pairs`는 외부에서 **이미 입증된** B3 equivalence witness의 입력 계약이다. 음성 판정과 모순되면 실패하고, 완전한 cross-pair 긍정 근거가 없으면 추가 병합하지 않는다. v3 자체 B3 witness producer와 최종 서비스 wiring은 이번 단계에서 실행하지 않았다.

기존 rc2 `models/events/features.py`는 Event semantic/trigger/role/Time/document 채널과 presence를 제공한다. `runtime/eventframe/event_identity.py`는 후보 pair score·complete-link를 수행하고, `event_closure.py`는 모든 member fact를 모아 strict B3 뒤 final state와 remap을 만든다. v3는 이 책임 분리를 유지하되 기존 checkpoint weight·DCE를 섞지 않는다. 새 Event head는 단계 5–7 source projection의 Event/Time state와 Trigger/role/Entity extra state를 **같은 direct-gather pass**의 request lease에서 받는다. 별도 backbone/DCE pass는 없다. pair interaction logits는 final cluster feature로 쓰지 않는다.

## scalar 사실과 transient tensor

`LocalEventState`에는 최종 local ID, 모든 member ID, 대표 exact source span, 모든 member trigger, 원문 role/Entity endpoint와 evidence ID, Time occurrence ID와 각 member support, 충돌/partial 상태만 들어간다. representative 외 member의 ACTOR/TARGET/PLACE/TIME도 보존한다. source가 같은 역할 fact만 중복 정리하면서 모든 provenance를 합친다. `member_to_cluster`와 `remap_time_attachments`는 최종 ID 기준으로 downstream endpoint를 만든다. 같은 좌표 역할이 서로 다른 Entity ID로 해소된 경우 `ROLE_ENDPOINT_CONFLICT`를 남긴다. `LocalEventState`와 장기 semantic/PUBLIC record에는 tensor가 없다.

요청 범위 owner 순서:

1. 고정 backbone L8/L10/L12 한 번 + 공유 DCE `SharedForwardLease` 한 번.
2. `EventTimeFeatureLease`: Event/Time/Trigger/role/Entity exact projection을 한 번 만들고 Time attachment와 Event member encoder가 함께 소비한다.
3. `EventMemberFeatureLease`: 8개 typed 채널(semantic, trigger, ACTOR, TARGET, PLACE, resolved Entity, Time, document)의 **sum/count** 및 same-event member state를 coreference와 final aggregation까지 보유한다. 없는 역할의 zero는 count 0으로 유지한다.
4. **최종 membership 확정 직후**, member lease가 살아 있을 때 `FinalClusterFeatureLease`를 만든다. cluster별 sum/count로 채널 평균, availability mask, conflict mask와 parameter-free mean reference를 계산한다. 관계(`RELATION`, 9번)와 Primary(`PRIMARY`, 10번)가 같은 final cluster ID/typed substrate를 보되 각자 필요한 learned projection은 그 단계에서 소유한다.
5. 마지막 consumer가 `release`할 때 final lease의 tensor 참조가 해제된다. member/time lease는 final aggregation 뒤 닫는다. 서비스 `.run()` 밖이나 PUBLIC serialization 뒤의 feature 재접근을 가정하지 않는다.

10번 연결에서 final lease에 고유 member ID별 transient state와 final cluster index, unique grounded role 요약을 추가했다. 이는 Primary의 segmented gate를 위한 request-scoped 참조이며 `LocalEventState`나 PUBLIC에는 복사되지 않는다. `RELATION`과 `PRIMARY`가 모두 반환할 때 해당 참조를 지우고, training loss graph가 backward에 필요한 activation을 별도로 유지한다. `source_mode`가 Gold oracle인지 예측인지 final lease에서 검사하여 runtime의 Gold feature 사용을 거부한다.

`EventFeatureProvenance`의 oracle/predicted membership·role 표시는 평가 메타데이터이며 모델 feature에 넣지 않는다. `score_event_identity`는 oracle lease를 거부한다. 임시 pair cap 4,096과 margin 0.0은 engineering 설정이며 서비스 threshold가 아니다. ABOUT/CAUSES/Primary head·loss·selection은 이 단계에서 구현하지 않았다.

## Entity representative consumer 분리

Entity identity closure가 고른 `LocalEntity.representative_candidate_id`는 Gold oracle과 predicted runtime의 공통 deterministic source selector 결과다. Event의 resolved Entity 채널 `ENTITY:<local_entity_id>`는 그 candidate의 ENTITY/L12 exact state를 그대로 사용하며, 별도의 earliest mention fallback이나 display-only 대표를 두지 않는다. PUBLIC `canonical_name`과 evidence span도 같은 `LocalEntity.text/start/end`를 사용한다.

ASSERTED_BY의 `ASSERTOR_ENTITY:<local_entity_id>`는 이 대표와 독립적으로 cluster의 모든 `ENTITY_MEMBER:<candidate_id>` state를 source-order로 모아 mean한다. 대표가 대명사에서 뒤의 명시 mention으로 바뀌어도 이 all-member inventory와 평균 수식은 바뀌지 않는다. 따라서 Event representative channel과 ASSERTED_BY all-member channel의 책임을 서로 대체하지 않는다.

## 검증 범위

`event-coverage-report.json`: 기존 train 400기사 EventMention 4,422, 최종 cluster 3,908, 다중 member cluster 401, same-event 양성 pair 675, 다른 occurrence eligible 음성 33,399. role evidence 6,656/6,656, Time attachment support 2,302/2,302가 최종 remap에 남았다. 기존 train engineering50의 same-event 양성은 104개다. 이는 Gold oracle 구조 검사이며 예측 품질이 아니다. 실제 pretrained checkpoint load·optimizer step·tiny-fit·본학습·서비스 threshold 선정은 0이다. 단계 2의 dev Gold blocker가 지속된다.
