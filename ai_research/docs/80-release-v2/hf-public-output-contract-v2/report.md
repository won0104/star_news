# HF Public Output Contract V2

## 결론

Release V2의 기본 HF pipeline output을 `articlelocal-kg-public-v2`으로 전환했다. 모델은 재학습하지 않았고 optimizer step은 0이며, Gold380 refresh에서 선택된 checkpoint SHA는 모두 유지됐다. public `nodes[]`와 `edges[]`는 현실 의미 identity와 현재 실행되는 semantic relation만 포함한다.

## 요청 질문에 대한 답

1. **V1 노출 객체** — EventFrame 기반 EVENT, LOCAL_EVENT, LOCAL_ENTITY와 MEMBER_OF_EVENT가 public graph에 함께 노출됐다.
2. **불필요한 이유** — 이 객체들은 extraction·resolution 구현 단계이지 별도 현실 entity가 아니다. public ontology에 함께 두면 동일 사건/개체가 이중 node로 보인다.
3. **V2 node kind** — ARTICLE, EVENT, STATEMENT, ENTITY, TIME의 닫힌 집합이다.
4. **V2 edge type** — COVERS, CONTAINS_STATEMENT, MENTIONS, ACTOR, TARGET, PLACE, OCCURRED_ON이다. ASSERTED_BY/ABOUT/CAUSES/SUBEVENT_OF는 현재 비승격 상태라 만들지 않았다.
5. **LocalEvent collapse** — runtime이 결정한 LocalEvent마다 deterministic public EVENT ID 하나를 만들고 member EventFrame은 evidence로 옮긴다. assembler가 text 유사도로 다시 합치지 않는다.
6. **LocalEntity collapse** — runtime LocalEntity마다 public ENTITY 하나를 만들고 member EntityMention을 evidence로 옮긴다. unresolved mention은 node가 아니다.
7. **member evidence 위치** — EVENT.evidence[]와 ENTITY.evidence[]에 `[start,end)` 원문 span과 prediction ID를 보존하며 raw lane은 source_lanes/evidence에도 남는다.
8. **대표자 손실 여부** — 대표자는 display anchor일 뿐이다. representative가 member 및 evidence에 포함되는지 hard validation하며 전체 member evidence를 함께 보존한다.
9. **relation endpoint remap** — 기존 semantic edge의 EventFrame/LocalEntity endpoint를 resolved public EVENT/ENTITY ID로 remap한다. 같은 semantic endpoint pair는 evidence/provenance를 합쳐 deterministic dedupe한다.
10. **unresolved evidence** — fake ENTITY/EVENT를 만들지 않고 `evidence.unmaterialized`와 `source_lanes`에 보존한다.
11. **Neo4j node** — Article, Event, Statement, Entity, Time label만 생성하면 된다. global identity merge는 downstream 책임이다.
12. **breaking change** — schema가 v1 runtime graph에서 `articlelocal-kg-public-v2`으로 바뀌며 LOCAL_EVENT/LOCAL_ENTITY node와 membership edge가 public graph에서 사라진다. v1 release와 assembler는 그대로 남아 있다.

## Replay evidence

- 실제 Gold380 runtime replay articles: 2
- EVENT member evidence: 20 → 20
- ENTITY member evidence: 67 → 67
- Remapped semantic source edges: 1248/1248
- Dangling edge: 0
- Fake node: 0
- Contract tests: 25/25

Gold380 full-refresh에서 발견된 초장문 Participant/Entity-resolution OOM blocker는 이 serialization 작업으로 해결하거나 숨기지 않았다. 이 결과는 public ontology contract 완료 판정이며, 기존 runtime readiness 판정을 뒤집지 않는다.
