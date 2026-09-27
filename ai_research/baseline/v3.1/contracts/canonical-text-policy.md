# r06.0 span-first canonical text / 최소 편집 정책

`runtime/v3_pretraining/canonical_text.py`는 final scalar semantic 결과를 서비스 표시문으로 바꾸는 비학습 결정 규칙이다. 규칙 버전은 `v3-span-first-minimal-edit-r06-v4`이다. canonical text는 Gold target, identity key, Primary 입력이 아니며 backbone/DCE를 실행하지 않는다. r06.0 exact-span annotation 계약도 바꾸지 않는다.

## 표시문과 source evidence

Event/Statement의 accepted source span이 표시문의 본체다. `canonical_text`는 열거된 어미 정리나 검증된 대명사 치환 때문에 원문의 연속 substring과 달라질 수 있지만, 모든 `SourceGrounding`과 node/edge evidence는 계속 `raw[start:end] == text`를 만족한다. `CanonicalTextResult`는 사용 grounding ID, exact source grounding, 적용 규칙, source/display 편집 범위, audit 이유, 사실 불변 조건을 함께 반환한다.

edit의 `display_start/display_end`는 최종 표시문 좌표다. ending/grounded replacement/frame edit의 표시 substring은 `replacement`와 같아야 한다. `CLAUSE_SELECTION`은 최종 descendant 범위 안의 비어 있지 않은 좌표를 가져야 한다. PUBLIC validator가 source 좌표와 final display 좌표를 각각 검사한다.

## Event 결정 순서

1. 완결된 원문 member span을 그대로 둔다. `현금 공급 중단`, `이스라엘과 하마스 간 휴전` 같은 다단어 명사형은 제한된 사건 명사 목록에 없더라도 조사·연결형 fragment가 아니면 보존한다.
2. 원문 span의 부정·조건·대조·수량·시점·양태를 삭제하지 않는다. final cluster에서 이 표면 marker를 더 많이 가진 member는 표시 anchor 후보에서 우선할 수 있다. marker 수가 같으면 기존 representative를 우선하며 길이는 tie-break가 아니다. 이는 결정적 surface heuristic이지 일반 의미 이해 또는 품질 점수가 아니다.
3. Event member의 terminal trigger가 실제 연결형 predicate를 지지하면, 표면에 이미 있는 `-았/-었/-였` 과거형의 `-고/-으며/-지만/-는데/-으나`를 `-다` 종결형으로 닫는다. `-했/-됐` 축약형도 같은 과거 의미를 보존한다. 예를 들어 `상을 받았지만`은 `상을 받았다.`가 되고 `하지 않았지만`은 `하지 않았다.`가 된다. 후행 절은 붙이지 않는다.
4. 시제가 없는 열거된 `하다/되다` 연결형은 terminal trigger와 안전한 동사 어간이 일치하고, 같은 source clause의 동일 인용·괄호 scope에 명확한 후행 과거형(`-았다/-었다/-였다/-했다/-됐다`) 또는 현재형(`-한다/-된다/-는다/-난다`)이 있을 때만 그 시제로 닫는다. `T1을 구매해 … 출전했다`는 `T1을 구매했다.`, `T1을 구매해 … 출전한다`는 `T1을 구매한다.`가 된다. 후행 predicate는 시제 근거로만 사용하고 표시문에 복사하지 않는다. 바로 뒤 격조사, 양태·전언 표현, scope 이탈, trigger 불일치, 안전한 어간이 아닌 `피해/오해/저해/침해` 등은 변환하지 않는다. 확인된 연결형 후보는 다단어 명사형 판정보다 먼저 처리하며, 시제 근거가 없으면 `FALLBACK_SOURCE_SPAN`을 유지한다.
5. 한 단어 bare predicate가 무엇을 가리키는지 알 수 없을 때만 `CanonicalSourceView`의 같은 최소 source clause를 사용할 수 있다. 다른 문장·별도 사건·reporting scope를 흡수하지 않는다.
6. `그는/이는` 또는 `이를/그것을`의 바로 그 원문 occurrence가 기존 role evidence로 잡혀 있고, 그 evidence의 Entity endpoint가 하나로 `RESOLVED`된 경우에만 치환을 검토한다. 한 표시문 안의 모든 대명사 occurrence와 endpoint는 첫 치환 전 source 좌표에서 확정한다. 실제 display 치환은 source 위치의 역순으로 적용하고 기존 edit 범위를 매번 rebase하므로, 앞선 장문 ACTOR 치환이나 반복 표면형이 뒤 TARGET의 원문 근거를 바꾸지 않는다. alias는 같은 Entity ID에 이미 연결된 exact 원문 role surface 중에서만 고른다. 다른 공동 ACTOR/TARGET, 단순 same-event member, unresolved·복수 endpoint는 치환 근거가 아니다. 동일 Entity의 다른 alias가 표시문에 이미 있으면 두 번째 alias를 추가하지 않는다. predicate root, Time, 부정·조건·양태·인용 scope 호환성도 계속 요구한다. bare safe-active predicate의 기존 ACTOR/TARGET frame 보강은 이 대명사 규칙과 별도다.
7. 완결 span에 ACTOR·PLACE·TIME이 없다는 이유만으로 채우지 않는다. 자동 PLACE 삽입과 다단어 완결 Event의 생략 ACTOR 접두 보강은 하지 않는다. unresolved/conflict 또는 근거 부족이면 원문과 사유를 유지한다.

## Statement 결정 순서

Statement type과 Assertor는 PUBLIC의 별도 칸/관계로 유지한다. 따라서 완결 명제 `대응이 적절했다`를 `전문가는 …라고 평가했다`로 확장하지 않는다. `-다고`처럼 finite form이 내부에 명시된 안전한 인용 연결형만 정리한다. 예를 들어 `내년에 매출이 늘어날 수 있다고`는 `내년에 매출이 늘어날 수 있다.`가 되며 가능성·시점은 그대로다. 임의의 `-고/-며` 절단, 발화자 생성, 예측 강도 변경은 하지 않는다.

연속 복수 문장 Statement span은 단일 clause에 들어가지 않아도 원문 전체를 유지한다. 안전한 ending 규칙이 없거나 명제가 불완전하면 주변 reporting clause를 붙이지 않고 `FALLBACK_SOURCE_SPAN`과 사유를 남긴다. `ASSERTED_BY`, Statement type, source evidence는 canonical display와 독립적으로 유지된다.

## Lifecycle과 불변식

`CanonicalSourceView`는 PUBLIC projection 요청당 한 번 만들고 선택된 Event/Statement가 공유한다. process cache나 tensor가 없으며 추가 backbone/DCE 호출도 없다. `LocalEventState.member_groundings`는 final cluster member의 ID/start/end/text만 보존한다.

기존 `GROUNDED_R2` 외부 mode 이름과 진단용 `SOURCE_ONLY` projection 계약은 유지한다. 두 mode의 node identity/kind, edge, relation 방향, Primary score/status, 선택 집합, persistence 상태는 같아야 한다. 차이는 canonical display/status/provenance와 그 표시에 실제 사용한 추가 exact evidence뿐이다. canonicalizer는 identity, membership, Trigger, role/relation endpoint 또는 Time projection을 변경하지 않는다.

## 알려진 제한

이 정책은 범용 한국어 형태소 분석기나 생성기가 아니다. `-던/-았던/-었던` 관형 과거와 `-면/-으면/-다면/-더라도` 조건형은 사실형으로 바꾸지 않는다. 이미 완결된 `-수 있다/-수 없다/-할 것이다/-될 것이다/-것으로 예상된다` 등의 양태·미래형과 span 내부의 `그러나/반면`, 부정·조건 표지도 보존한다. 불규칙 활용, 생략 대상이 불명확한 문장, 복수 후보, 충돌 endpoint, 피동 frame 재배열은 source 또는 최소 clause fallback으로 남는다. 합성 fixture는 규칙 회귀 기준이며 모델 품질이나 일반적인 의미 이해의 증거가 아니다.
