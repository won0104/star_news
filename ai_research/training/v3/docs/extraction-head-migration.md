# 단계 5 — r05.3 exact 추출·속성 head 연결

## 실행 경로와 상태

`TrainGoldReader`의 검증된 기존 train Gold → `TargetCompiler` → `TargetCollator`의 **전체 sentence+bridge window** → 고정 L8/L10/L12 backbone 1회 → 공유 DCE 1회 → `ExtractionGoldAdapter`의 task별 loss다. Gold ID/label은 adapter 안에서만 쓴다. 실제 pretrained weight는 이 단계에서 적재하지 않았고, unit test는 synthetic `BackboneOutput`으로 finite loss/backward를 검증했다. `semantic_proposer`, `semantic_boundary`, `semantic_validity`, `trigger`, `participant`, `entity_mention`, `time_mention`, `statement_type` 8개가 fresh registry에 준비된다. 나머지 11개는 미구현으로 남아 full-model 요청이 실패한다.

기존 `JointSpanProposalHead`, `CanonicalSpanRepresentationV3`, `TriggerBoundaryHead`, `ParticipantBoundaryHead`, `EntitySpanNativeHead`, `TimeExpressionSpanNativeHead`, `StatementTypeHead`, `CandidateSpanEncoder`의 책임·topology를 재사용한다. `CandidateSpanEncoder.forward_runtime_direct_states`는 이미 계산한 sentence state만 받아 기존 layer별 direct gather를 실행한다. 새로운 `ExactSourceSpanBridge`는 window 안에서 이 direct gather를 쓰고, window를 가로지르는 span에서만 **같은** L8/L10/L12와 DCE의 양 끝 표현을 결합한다. task별 독립 DCE나 backbone 재실행은 없다. 기존 head 참고 논문과 변경 전 provenance는 `models/spans/semantic.py`, `models/context.py`의 모듈 문서와 `baseline-map.md`를 따른다.

| 책임 | Gold target → 학습 loss → decode/consumer |
|---|---|
| Event/Statement 후보 | exact span의 window 안 joint cell과 전역 start/end source token·cross-window link에 positive loss. 미기록 임의 semantic span은 음성화하지 않음 → source-token 후보 → boundary/validity/속성 |
| 의미 boundary | 기존 canonical boundary의 window 안 판정 + 모든 span의 signed start/end 문자 잔차 SmoothL1. cross-window 양 끝도 같은 target 수에 포함 → end-exclusive 원문 좌표 |
| 의미 validity | 기존 canonical 판정(window 안) + endpoint span 판정(전체) positive loss. rank·role 유무와 독립 → 의미 적격성 후보 |
| Trigger | L8 기존 boundary + 전역 endpoint + exact residual/long-span link. Event 삭제 hard gate 없음 → 원문 occurrence |
| Participant | Event span feature로 조건화한 기존 B2 ACTOR/TARGET/PLACE boundary + role span score, 전역 endpoint/residual. NER 입력은 필요하지 않음 → role source span → 6번 Entity union |
| EntityMention | L12 boundary + 기존 nested span-native 5-type classifier; label 순서 `PERSON, ORGANIZATION, LOCATION, PRODUCT, GENERIC`. signed residual/긴 span feature 유지 → 6번 Entity 후보 |
| TimeMention | L10 boundary + generic Time span-native score. normalized null도 같은 추출 양성 → 7번 normalization/attachment |
| StatementType | Gold Statement에 대해 기존 `StatementTypeHead` CE; `FORECAST, CLAIM, EVALUATION`, 존재 label과 분리 → Statement 속성 |

같은 source span의 sentence/bridge 중복은 원문 절대 좌표로 닫고, 다른 위치의 반복 언급은 남긴다. runtime decoder는 전역 bridge token의 start/end 후보를 bounded pair로 만들고, bridge의 예측 signed residual을 문자 좌표에 적용한다. 예측 float 잔차만 정수 문자 위치로 decode한다. **Gold 좌표·잔차를 반올림하거나 128-token에 맞춰 절단하지 않는다.** `DecodeResult.partial`은 endpoint/pair 예산에 걸리면 true이며 invalid 예측과 scored pair 수를 별도로 낸다. Entity/Statement decode는 등록된 type head의 label을 포함하고, Participant decode는 Event alignment와 role을 요구한다.

## coverage와 검증 범위

`extraction-coverage-report.json`은 기존 train engineering50의 source span target 6,906개(semantic 1,844, Trigger 827, Participant 1,296, Entity 2,307, Time 632)를 정확하게 왕복했고, signed residual 204개와 cross-window 1개를 기록했다. 학습 adapter의 candidate cap은 없고 target 누락 0이다. 임시 runtime budget `64 start / 64 end / 256 pair`에서는 optimistic Gold endpoint cardinality만 봐도 50기사 중 Entity 10기사, semantic 4기사는 전체 Gold 후보 수를 담을 수 없다. 해당 decoder는 `partial`을 반환한다. 이는 fresh random 모델의 recall이나 production threshold 평가가 아니다. budget 확대·candidate quality 평가는 본학습/운영 정책을 선발하는 후속 단계에서 별도 검증한다.

`tests/test_v3_extraction.py`는 검증된 train Gold 1기사와 합성 fixture에서 8 loss의 finite backward, DCE/proposer/canonical/direct gather·각 head의 gradient, nested GENERIC, 한 token·Statement-only head fixture, signed gap/cross-sentence/cross-window decode, Event-conditioned ACTOR, Primary adapter 변경에 대한 extraction 불변성을 확인한다. 기존 rc2 selective capture와 scalar carrier 관련 회귀 17개도 통과했다. 실제 pretrained model의 raw article 품질, predicted-span exact F1, class calibration, tiny-fit, optimizer step는 이 단계에서 검증하지 않았다. 전체 Gold intake는 dev `136.json` 오류 때문에 여전히 `BLOCKED`다.
