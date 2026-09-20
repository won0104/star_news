# v3 PUBLIC 선택·투영 계약 (12번)

`V3ConstructionResult`는 요청 범위 scalar semantic 결과다. `RawArticle` 원문은 canonical text 및 evidence 검증의 마지막 소비 시점까지 호출자가 유지한다. `project_public`은 이 결과를 읽어 **선택된 proposition부터** 노드와 간선을 만든다. 모델의 Event/Statement `primary_score`, status, producer version은 relation logit 및 구조 관계와 별개 필드다. 구성 결과에는 tensor나 DB identity가 없다.

- 입력 Event/Entity closure는 `PREDICTED`이고 Event closure의 article version·content SHA가 원문과 같아야 한다. 모든 source span·role·Time·Assertor·ordered relation endpoint를 투영 전에 검증한다. final local ID만 사용한다.
- 기본 선택은 전체 EventCluster·Statement이다. 외부가 두 kind의 선택 ID 집합을 주거나 **외부가 정한** 유한 threshold를 넘길 수 있다. threshold와 명시 선택은 동시 사용하지 않는다. 누락 점수의 0 대체는 없고, 명시한 `diagnostic_unfiltered`일 때만 진단 출력한다. threshold는 모든 후보에 학습된 점수가 있어야 쓴다. quota/Top-K/production threshold는 없다.
- 선택된 Event의 ACTOR/TARGET/PLACE, 선택된 Statement의 resolved ASSERTED_BY가 가리키는 Entity만 공개한다. SPAN_ONLY/미해결 Assertor·role은 내부 근거로 남고 fake Entity는 없다. `MENTIONS`는 살아남은 Entity에만 부가한다.
- 선택된 Event의 실제 `LocalTimeFact`가 가리키는 Time 중 `YYYY`, `YYYY-MM`, `YYYY-MM-DD`의 유효한 단일 calendar point만 PUBLIC Time과 OCCURRED_ON으로 만든다. FY·interval·null·미연결 Time은 내부 construction에 남는다. 연도를 월/일로 보정하지 않는다.
- ABOUT/CAUSES는 선택 후 양 endpoint가 남을 때만 출력한다. 관계 때문에 proposition을 부활시키지 않는다. `CAUSES`는 방향이 있고 자기 관계는 금지한다.
- COVERS `isPrimary`는 학습 target이 아니라 선택된 Event의 **학습 완료된** raw score 최대값에 대한 projection 정책이다. 동점은 source start/end와 final local ID로 결정한다. Event 0개, 미학습/누락 score면 `PERSISTENCE_NOT_READY`이고 대표를 만들지 않는다. N1 Article 저장은 COVERS ≥1·정확히 하나의 isPrimary가 있을 때만 가능하다. 추론에서 zero-event인 경우는 별도로 반환한다.
- schema `articlelocal-kg-public-v3`는 v2.2와 별개다. `validate_public`은 노드/간선 필드 allowlist, Entity taxonomy, Time 정밀도, source offset, endpoint 연결성, semantic Entity/Time 생존 조건과 저장 전제를 검사한다. JSON Schema와 viewer adapter가 같은 version을 사용한다. serializer는 finite JSON과 pretty 출력을 지원한다.
- `project_neo4j_dry_run`은 순수 설명용 projection이다. local ID와 `backend_uuid: null`을 분리하고, 모든 UUID 및 EntityType 세분 매핑을 `unmapped`에 기록한다. Event.title, Statement.text/type, Entity name/internal type, Time value/year/month/day, COVERS.isPrimary 등의 제안만 만든다. `primary_score`는 PUBLIC scalar로 유지하며 backend 저장 속성은 미확정으로 보고한다. PUBLIC의 저장 전제와 backend의 미완성 ID/type 매핑도 별도 상태다. DB write, global matching, Story, MySQL ID, 계층형 Time node 생성은 없다.

검증은 합성 final local closure fixture 및 기존 v2.2 회귀 테스트로 수행했다. 3개/10개 Event 선택, Statement-only, score 누락/미학습, FY·interval·null, SPAN_ONLY PLACE, endpoint 손상, schema/viewer/dry-run을 확인했다. 현재 모델은 fresh-init Primary status이므로 실제 예측은 저장 준비가 아니며 production selection이나 DB persistence는 검증하지 않았다. 단계 2의 dev Gold `136.json` blocker는 유지된다.
