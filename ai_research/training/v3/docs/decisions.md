# V3 단계별 결정과 미확정 경계

## D1. 변경 경로와 version namespace

- v3의 새 코드 namespace는 이 프로젝트 안의 `models/v3_pretraining/`, `runtime/v3_pretraining/`, `training/v3_pretraining/`을 기본으로 한다. 실제 entry point의 파일명·CLI는 해당 코드를 처음 구현하는 단계에서 확정한다. 기존 `release/`와 `gold_verified/`, archive/EOT 자료는 수정하지 않는다.
- 단계 문서와 상태 파일은 `ArticleLocal-KG-DeBERTa/docs/v3-pretraining/`에 둔다. 새 검증 출력은 필요 시 이 경로의 `reports/step-N/`에 둔다. 이 단계는 문서 6개만 생성한다.
- 기존 개발 `models/`·`runtime/`은 rc2 Python 소스와 tree hash가 같지만 release-local JSON 경로는 다르다. v3 변경은 새 factory/config/adapter를 통해 격리하고 rc2 원본을 보존한다.

## D2. source/label 우선순위

- `gold_verified/*.json` + r05.3 guideline/schema + `data/processed/gnews/gnews-1k-spring-preprocessed-v1.0.json`을 새 학습 truth로 고정한다. Gold 파일명 숫자는 join key가 아니다. 단계 1에서 500개 JSON 파일의 **바이트 hash만** 고정했으며 valid/unique article 수와 의미 정확성은 판정하지 않았다.
- `training/scripts/train.py`의 기존 Gold adapter는 construction Gold v2.x만 허용하므로 새 Gold에 억지로 연결하지 않는다. 이전 Gold380 task weight는 rc2 검증 기준으로만 둔다.
- rc2 historical CPU/FP32 결과는 해당 frozen bundle의 비교 기준이다. v3 fresh model 품질/메모리의 증거로 사용하지 않는다.

## D3. N1 DB/ERD와 모델 책임

N1 [DB/ERD](https://app.notion.com/p/3e1ddb07b10f802e87bbc372bac89005) fetch 결과는 `2026-09-20T08:10:11.138Z` 기준, page last edited `2026-09-20T08:09:42.763Z`, Notion verification `unverified`였다. 모델은 article-local Event/Statement/Entity/Time과 근거 및 관계 후보를 낸다. N1의 FastAPI는 분석과 Neo4j 읽기·쓰기를, Spring Boot는 MySQL 읽기·쓰기와 API 조합을 맡는다. 따라서 DB UUID `nodeId`, MySQL ID, NewsOrganization 결합, Story/global Event matching, timestamps, embedding 저장은 추출 모델의 local ID가 아니다.

- N1의 `ASSERTED_BY`는 Statement→Entity이고 `CAUSES`는 Event→Event 방향 관계다. N1 `ABOUT`는 Statement→Event **및** Statement→Entity를 허용하지만 새 Gold 학습은 Statement→EventCluster만 사용한다. `SUBEVENT_OF`와 Story/Topic/User 관계는 이번 학습 ontology 밖이다.
- N1 EntityType은 PERSON/COMPANY/ORGANIZATION/GOVERNMENT_AGENCY/NEWS_ORGANIZATION/LOCATION이며 Gold에는 PERSON/ORGANIZATION/LOCATION/PRODUCT/GENERIC이 있다. 특히 PRODUCT/GENERIC 및 세분화된 기관 type의 mapping은 1:1로 확정할 수 없다. 후속 adapter가 임의로 직렬화하지 않도록 미확정으로 기록한다.
- N1의 `Time.timeKey`는 `YYYY`, `YYYY-MM`, `YYYY-MM-DD`; `granularity`는 YEAR/MONTH/DAY다. 새 내부 TimeMention의 미정규화·구간/반복 표현을 달력 날짜로 위장하지 않는다.
- N1은 저장된 Article에 최소 하나의 `COVERS`와 정확히 하나의 `isPrimary=true`를 요구한다. Gold는 EventCluster 최고 순위 동순위를 허용하며 `is_primary`를 저장하지 않는다. zero-event 또는 선택 Event 없음에 대한 persistence 정책은 FastAPI/서비스 경계에서 합의할 사항이다. fake Event를 만들거나 학습 rank를 바꾸지 않는다.
- N1에서 `PLACE`의 대상은 Location으로 표기되지만 현 PUBLIC은 Event→Entity로 구현돼 있다. r05.3은 PLACE의 Entity endpoint 또는 SPAN_ONLY를 허용한다. v3 내부 계약을 먼저 검증하고 DB adapter mapping을 별도로 결정한다.
- 현 `runtime/graph/neo4j.py`는 연결 없이 Cypher를 생성하며 `ArticleLocalKGNode.id`를 쓴다. N1 `nodeId` UUID 영속화 adapter로 그대로 간주하지 않는다.

## D4. 후속 단계 전제

단계 2는 현 Gold 전체의 schema/join/offset/reference/census와 train 소속 engineering50을 결정해야 한다. 이 단계에서는 test 내용으로 fixture를 선택하지 않았다. v3 head, threshold, schema, API, 실제 DB 작업을 변경하지 않았다.

## D5. 단계 2의 split·Gold intake 결정

- 기존 seed-41 `round_assignment.json`은 현재 기사 단위 train/dev/test 소속 확인에만 사용한다. 부분 Gold 500기사의 label 분포로 1K split의 최종 적합성을 승인하거나 재설계하지 않는다.
- 전체 현재 Gold의 기계적 유효성은 검사하되, feature census·engineering50·tiny 후보 선정은 검증 통과한 기존 train Gold에서만 수행한다. 기존 dev/test Gold는 모델·정책 디버깅, tiny-fit, architecture/threshold/checkpoint 선택에 사용하지 않는다.
- `gold_verified/136.json`의 `TM6` 혼합 granularity 구간은 자동 수정하지 않고 quarantine한다. dev 소속 1건이라도 전체 현재 Gold 통과 조건이 충족되지 않아 단계 상태는 `BLOCKED`다. 원본 검토 후 전체 검사를 재실행해야 한다.
- `engineering50-manifest.json`의 40/10은 기존 train 안의 구현용 분할이며 최종 train/dev/test 재분할이 아니다. 현재 subset은 오류 해결 전 잠정 개발 목록이다.

## D6. 단계 3의 손실 없는 문자 target

- 기존 128-token sentence view는 보존하고, Gold 비의존 bridge window를 같은 원문에서 결정한다. 해당 window를 기존 rc2 cache key와 혼동하지 않도록 새 layout policy·tokenizer hash·view/input hash를 구분한다.
- exact Gold span의 token 내부/공백 boundary는 부호 있는 문자 잔차를 보존한다. 한 window를 넘는 span은 양 끝 window reference를 보존한다. 이는 compiler의 표현 계약이며 현재 head의 학습 지원 증거가 아니다.
- semantic 임의 미기록 span을 자동 음성으로 만들지 않는다. closed-world 음성은 guideline이 명시한 ABOUT/CAUSES와 검증된 article-local membership·attachment·resolution universe에만 한정한다.

## D7. 단계 4의 공유 owner·학습 경계

- v3는 기존 여러 checkpoint의 DCE를 혼합하지 않고 단일 fresh DCE를 소유한다. 공유 L8 DCE와 proposer만 현재 forward에 연결됐으며 다른 18 task는 registry에서 미구현으로 남긴다. `canonical_span` 등 생성된 learned module의 parameter는 초기화 manifest에 기록하되 Gold loss 연결을 완료한 것으로 표시하지 않는다.
- 고정 backbone은 외부 주입으로 분리한다. 기존 rc2 `@inference_mode` provider의 tensor를 학습 core에 그대로 전달하지 않고, 새 `FrozenBackboneFeatureBuilder`가 고정 producer를 `no_grad`로 한 번 실행해 일반 tensor를 제공한다. 실제 pretrained load/성능 검증은 이번 단계에서 하지 않는다.
- compact tensor handoff는 요청 안에서만 사용하고 producer identity, content/window alignment, ordered IDs/mask를 검증한다. 마지막 consumer 후 `close`하며 장기 semantic/PUBLIC carrier에는 scalar만 허용한다. frozen source key와 trainable key는 분리하고 train-mode dropout 호출에는 별도 invocation ID를 요구한다. 실제 persistent cache는 만들지 않는다.
- factory는 이전 task weight를 자동 load하지 않는다. 등록 시 동일 fresh run ID를 검사하지만 호출자가 주장한 ID 자체를 암호학적으로 증명하지는 않는다. 이후 단계 13에서 생성자 파일 접근과 save/reload provenance를 더 강하게 확인한다. 전체 Gold blocker는 그대로다.

## D8. 단계 5의 exact span과 임시 candidate 예산

- Gold-positive semantic target은 순위·role 유무와 분리하고 미기록 임의 semantic span을 자동 음성화하지 않는다. 후보 제안·boundary·validity의 실제 Gold loss는 분리한다. 억제용 negative 정책과 calibration은 별도 검증이 필요하며 positive-only fixture 통과를 품질 증거로 쓰지 않는다.
- in-window span에는 기존 `CandidateSpanEncoder` direct gather·canonical verifier를, cross-window span에는 동일 backbone/DCE의 양 끝 표현을 쓴다. signed 문자 잔차는 회귀 target으로 보존하고 Gold를 token 경계로 반올림하지 않는다. 예측 잔차만 runtime에서 정수 문자 위치로 decode한다.
- 임시 raw decoder 예산 64 start / 64 end / 256 pair는 `PROVISIONAL_ENGINEERING_ONLY`이며 선택된 service threshold가 아니다. 실제 candidate 제한으로 누락 가능성이 있으면 `partial`과 계수를 반환한다. Gold teacher-forced loss에는 cap을 적용하지 않는다.
- GENERIC을 포함한 5-type Entity와 Event-conditioned role span을 같은 추출 단계에서 별도 생산한다. 두 경로의 union·identity·endpoint는 6번 책임이다. 기존 rc2 weight를 새 초기값으로 쓰지 않는다.

## D9. 단계 6의 Entity identity와 타입 충돌

- NER·role·미래 Assertor의 exact source 근거를 우선 합치고, role evidence는 NER-only priority보다 먼저 후보 cap에 예약한다. 확정 ACTOR/TARGET에 4-type이 없을 때만 `GENERIC` fallback을 연다. 예측 `PROPOSED` role은 NER와 좌표가 같아도 자동으로 확정하지 않는다.
- 동일 좌표·타입이라도 문맥 hint와 unhinted NER가 충돌하면 별도 후보로 둔다. 다른 surface의 alias는 learned symmetric coreference에 맡긴다. Gold ID는 학습 oracle에서만 사용하고, 예측 hint는 `CTX:` 로컬 값만 허용한다.
- Gold cluster에 서로 다른 concrete mention type이 실제로 존재한다. 이때 identity와 ACTOR/TARGET endpoint는 보존하고 local type은 null, `observed_types`와 `RESOLVED_TYPE_CONFLICT`를 반환한다. 타입을 다수결이나 임의의 Gold cluster canonical type으로 가정하지 않는다.
- 128 candidate와 pair argmax는 임시 engineering 정책이다. teacher-forced Gold에는 cap을 적용하지 않는다. NER priority는 현재 양성 감독만 있으므로 서비스 억제 threshold를 정하지 않는다. 9번 Assertor producer, 14번 서빙 wiring 전까지 새 경로는 독립 adapter다.

## D10. 단계 7 Time precision과 attachment

- textual Time 존재, normalized value 감독 여부, 실제 Event attachment는 서로 다른 target이다. null normalized value도 extraction/attachment의 양성에서 제거하지 않는다. 임의의 같은 문장 Time을 attachment 양성으로 만들지 않는다.
- 내부 FY·동일 granularity interval·null은 손실 없이 남긴다. source rule은 exact text 또는 timezone이 확정된 상대 표현에만 값을 만든다. learned 문자 출력만으로 더 정밀한 날짜를 생성하지 않는다. calendar eligibility는 단일 유효 YEAR/MONTH/DAY로 제한하고 실제 PUBLIC 선택 Event 연결성은 12번에 남긴다.
- 임시 attachment score threshold 0.0과 pair cap 4,096은 engineering 설정이며 production calibration이 아니다. Gold loss는 이 cap을 사용하지 않는다. tensor는 request lease의 마지막 consumer 이후 해제한다.

## D11. 단계 8 final Event membership과 tensor owner

- same-event는 동일 occurrence의 supervised pair이며 인과·선후·주제·Time/Entity 공유만으로 merge하지 않는다. 미평가 pair는 negative가 아니다. learned complete-link 뒤의 strict B3 witness는 외부에서 입증된 것만 받으며 모순된 음성은 거절한다. 현재 B3 witness producer와 서비스 wiring은 연결 전이다.
- final `LocalEventState`는 모든 member의 exact Trigger/role/Time 사실과 remap·conflict/partial 상태만 갖는다. 대표 member 하나의 feature를 cluster 전체의 semantic fact로 대체하지 않는다.
- Event/Time/Trigger/role/Entity 표현은 같은 backbone/DCE·direct-gather pass의 request lease에서 소비한다. 8개 채널 sum/count로 없는 역할의 zero dilution을 막는다. 최종 membership 뒤 parameter-free mean reference를 만들고 9번 관계와 10번 Primary가 모두 release할 때 tensor를 해제한다. 각 소비자의 learned projection과 loss는 해당 후속 단계에서 구현한다.
