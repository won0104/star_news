# Construction Gold v3 — Curated RC Guideline v3

## 0. 상태·계보·권한

- Revision: `v3-guideline-r04`.
- Parent guideline: `v3-guideline-r03`.
- Parent Gold schema: `articlelocal-kg-construction-gold-v3.0-curated-rc1`.
- 이 문서는 `v3-guideline-r03`의 의미 계약을 계승하면서, Round04–06 review에서 반복적으로 확인된 ontology/role/proposition/relation policy gap을 명시적으로 닫는 후속 guideline이다.
- 기존 `curated_gold_rc.json`, `guideline_rc.md`, `guideline_rc_v2.md`와 기존 Gold/review artifact는 과거 실험 provenance를 위해 immutable하게 유지한다. 기존 RC1 schema의 구조 계약은 유지하고 guideline version 필드만 backward-compatible하게 확장한다.
- 기존 r02/r03 Gold와 기존 curation/review record의 guideline version 및 source guideline SHA는 다시 쓰지 않는다. r04를 실제로 적용해 새로 adjudicate한 record만 r04를 기록한다.
- 본문과 offset은 immutable하다. title/publishedAt/외부 지식/모델 score로 label을 만들지 않는다.
- 모델이 잘 학습하기 쉬운 형태로 의미를 바꾸지 않는다. candidate universe, threshold, representation, runtime 구조는 annotation truth를 결정하지 않는다.
- parent provenance는 보존한다. 새 검토는 실제 주체의 `AI_REVIEWED`, 독립 제안의 `AI_INDEPENDENT_REVIEWED`, 조정의 `AI_ADJUDICATED`를 curation record에 남긴다. HUMAN_REVIEWED를 사용하지 않는다.
- AI 검수 결과는 사람 검수 완료나 production 인증을 뜻하지 않는다.
## 1. 작업 순서

1. 본문 전체를 읽고 proposition, 인용, 실제 발생 여부, 양태 scope를 파악한다.
2. Event/Statement proposition 경계를 먼저 고정한다. splitter artifact와 semantic proposition을 혼동하지 않는다.
3. Event의 Trigger와 ACTOR/TARGET/PLACE/TIME filler를 검토한다.
4. Statement의 type과 Assertor를 검토한다.
5. Entity mention/identity와 Event occurrence identity를 고정한다.
6. 안정된 proposition/identity를 기준으로 ABOUT, CAUSES, SUBEVENT_OF를 판정한다.
7. 관계 판정 때문에 fake Event/Statement/Entity를 만들지 않는다.
8. 구조/offset/lineage/coverage/reference/self-edge/cycle을 검사한다.

RC1에서 사용한 특정 review 수량(예: 지정 proposition 수, targeted pair 수)은 과거 curation procedure의 provenance이며 이 guideline의 영구 의미 규칙은 아니다.

## 2. Event/Statement와 local semantic proposition

EVENT는 본문이 이미 발생·수행·관측됐다고 제시하는 독립 사건/행동/상태 변화/공식 performative다.
STATEMENT는 FORECAST(전망·예측·가능성·계획·의지·약속·희망), CLAIM(주장·소문), EVALUATION(평가·해석·권고)의 독립 명제다. 외부 사실 검증으로 type을 바꾸지 않는다.

한 node는 하나의 독립 semantic proposition이다. 단순 문법적 절, 쉼표, 모델 sentence ID가 경계의 정답은 아니다.
연결된 여러 행위라도 독립적으로 설명할 수 있는 실제 occurrence가 다르면 나눈다. 하나의 predicate에 묶인 목록/복합 theme는 기계적으로 쪼개지 않는다.

`proposition span = local semantic unit`, `context evidence = 필요한 경우 다른 문장 참조`로 분리한다.
공유 주어, 출처, 지시어 antecedent를 이해하려고 이전 문장을 읽어도 그 문장 전체를 proposition span에 넣지 않는다.
역할/Assertor evidence가 proposition 밖에 있다는 이유로 삭제하거나 local span을 복제하지 않는다.
실제로 한 명제를 여러 logical sentence 없이 표현할 수 없으면 원문 span을 보존하고 `HUMAN_REVIEW_REQUIRED`와 이유를 기록한다. local-model 성공을 위해 의미를 잘라내지 않는다.

review category:

- `LOCAL_PROPOSITION_PLUS_CONTEXT`: 핵심 명제 하나와 외부 출처/participant/context가 합쳐졌음.
- `MULTIPLE_PROPOSITIONS_MERGED`: 독립 명제가 여럿 결합됨.
- `SENTENCE_SEGMENTATION_ARTIFACT`: 약어/인용/소수점/괄호 등 splitter 오류.
- `TRUE_CROSS_SENTENCE_PROPOSITION`: 실제 논리 경계를 넘어서는 한 명제.
- `AMBIGUOUS`: 둘 이상의 해석이 남음.

### Article semantic scope

processed content와 offset은 immutable하지만, 그 안의 모든 문자열이 semantic annotation 대상인 것은 아니다.

기사의 사건·주장·평가·전망을 구성하지 않는 다음 편집·서비스 메타 텍스트는 그 자체만으로 Event/Statement를 만들지 않는다.

- byline / 기자명 / 이메일 / 사진·영상 credit
- `관련기사`, `공유하기`, 증권 위젯, 광고·navigation 등 UI 문자열
- 기사 작성 방식이나 자료 출처만을 알리는 정형화된 편집 고지
- 기사마다 반복 삽입되는 고정 상담·안내·법적 고지
- 본문 명제를 단순 반복·압축하는 제목·소제목·목록 label

이 문자열들은 원문에서 삭제하거나 offset을 다시 계산하지 않는다. annotation 대상이 아닐 뿐 source content에는 그대로 보존한다.

사진 caption이나 별도 블록이 본문의 다른 곳에 존재하지 않는 독립 사실 명제를 실제로 서술하는 경우에는 단순히 caption이라는 이유만으로 제외하지 않는다. 해당 문자열 자체가 독립 semantic proposition을 갖는지 판정한다.

metadata성 byline·기자·언론사 정보만으로 생략된 Assertor를 보충하지 않는 기존 원칙을 유지한다.

### Attribution carrier와 performative Event의 경계

단순 attribution carrier는 독립 Event를 강제하지 않는다. 실제 발표/요청/결정/발령은 행위 자체가 Event일 수 있다. 내포 forecast/claim을 실제 Event로 승격하지 않는다.

`말했다`, `밝혔다`, `전했다`, `설명했다`, `보도했다`, `비유했다`, `집계했다`, `경고했다` 같은 표면 동사만으로 carrier/Event를 결정하지 않는다.

판정 기준은 **전달되는 content를 제거한 뒤에도 그 행위 자체가 article-local occurrence로 독립적으로 보도되는가**이다.

다음은 기본적으로 attribution/reporting carrier다.

- 인용·주장·평가·전망의 source를 소개하기 위한 발화 동사
- 기사 또는 다른 매체가 내용을 전달했다는 사실만 나타내는 `보도했다`
- 주장 내용을 소개하기 위한 `설명했다`, `비판했다`, `비유했다`, `전했다`
- 수치나 연구 결과의 source를 소개하는 데 그치는 `집계했다`, `보고했다`

다음은 행위 자체가 독립 occurrence이면 Event가 될 수 있다.

- 공식 결정·발령·명령·공시·신청·제출·승인·거부
- 독립된 제도적 효력을 갖는 발표·공표
- 실제 요청·지시·촉구·제안 행위 자체가 기사에서 보도 대상인 경우
- 게시·발표·게재 행위가 시간·주체·대상과 함께 독립 occurrence로 서술되는 경우

같은 동사라도 문맥에 따라 carrier 또는 performative Event가 될 수 있다. lexical whitelist만으로 결정하지 않는다.

performative Event를 만든다고 해서 그 내부의 forecast/claim/evaluation content를 실제 Event로 승격하지 않는다.

### Negated occurrence

본문이 특정 occurrence의 **비발생·부재·미확인**만을 주장하는 경우, 존재하지 않은 occurrence를 positive Event로 만들지 않는다.

예:

- `새로운 부작용은 확인되지 않았다`
- `사고는 발생하지 않았다`
- `사람 간 전염 사례는 보고되지 않았다`

이 경우 해당 부재·미확인 내용은 필요하면 CLAIM으로 보존한다.

반대로 실제로 수행된 조사·검사·확인·관찰 행위가 독립적으로 서술되면 그 수행 행위 자체는 Event가 될 수 있다.

`확인되지 않았다`라는 부정 결과와 `104주간 추적 관찰했다`라는 실제 수행 occurrence를 혼동하지 않는다.

### Repeated Statement mentions

서로 다른 원문 span에서 독립적으로 실현된 Statement는 semantic content가 같거나 매우 유사해도 evidence/source/discourse provenance가 다르면 각각 보존할 수 있다.

예:

- 기사 lead가 미래 일정을 서술
- 뒤에서 기관의 인용문이 같은 일정을 다시 서술

현재 schema에는 StatementCoref가 없으므로 내용이 유사하다는 이유만으로 한쪽 Statement를 삭제하거나 하나의 span으로 합치지 않는다.

금지하는 것은 동일한 원문 span과 동일한 semantic proposition에 대한 중복 annotation이다.

후속 ABOUT 등의 target이 반복된 Statement 중 어느 것을 직접 지시하는지 article-local evidence만으로 확정되지 않으면 임의의 대표 Statement를 고르지 않고 UNRESOLVED로 남긴다.

Assertor는 실제 주장/평가/전망 주체다. 내부 명제의 주어가 아니다. 생략 source를 metadata의 기자/언론사로 채우지 않는다.

### Assertor supervision 권한

canonical Gold의 `assertor_status`와 `assertor` 값은 **검수되지 않은 alternative Statement–source pair 전체를 negative로 승인한다는 뜻이 아니다**.

확정 Assertor는 POSITIVE다. 별도 review에서 특정 Statement–source exact pair를 해당 Statement의 Assertor가 아니라고 확정한 경우 그 exact pair에 한해 `SAFE_NEGATIVE_PAIR`로 사용할 수 있다. AMBIGUOUS / UPSTREAM_REVIEW_REQUIRED / unresolved source는 UNKNOWN으로 남기며, 검수되지 않은 alternative source 후보를 단순히 Gold Assertor가 아니라는 이유로 negative로 만들지 않는다. `SAFE_NEGATIVE_PAIR`는 pair-local authority이며 같은 Statement의 다른 source 후보나 같은 source의 다른 Statement로 일반화하지 않는다. reviewed pair-local negative는 sidecar/review artifact에 저장할 수 있으며, canonical Gold의 `assertor_status`와 `assertor` 구조를 closed-world negative table로 해석하지 않는다.

## 3. Trigger

Trigger는 Event를 원문에서 lexical하게 식별하는 **최소한의 semantically sufficient event anchor**다.
가장 짧은 동사 선택이 목적이 아니다. `발표했다`, `증가했다`, `발생했다`는 단독으로 충분하다.
support/light verb이면 필요한 event-bearing 표현을 포함한다: `결정을 내렸다`, `발표를 진행했다`, `목소리를 높였다`, `손사래를 쳤다`.
ACTOR/TARGET/장소/시간까지 불필요하게 포함하지 않는다. 원문 없는 lemma를 만들지 않는다.
명사형이나 불가피한 role overlap은 허용하고 이유를 기록한다.

## 4. 의미역과 textual evidence

### ACTOR

semantic agent / initiator / controller. 실제 행위자·결정/요청/공표 주체·명시적 passive agent·명백한 공유 주어다.
문법적 subject나 causal natural phenomenon만으로 ACTOR가 되지 않는다. `강진이 발생했다`에서 강진은 ACTOR가 아니다.

### TARGET

핵심 non-agent participant다. patient/object/affected participant뿐 아니라 변화·발생·존재 predicate의 theme/phenomenon을 포함한다.
`매출이 증가했다`의 매출, `강진이 발생했다`의 강진이 TARGET이다. ACTOR가 아닌 아무 명사를 TARGET으로 채우지 않는다.
요청의 핵심 내용과 단순 수신자를 구분한다. Entity ontology가 허용하지 않는다고 역할을 삭제하지 않는다.

#### 수신자·도착지와 TARGET

TARGET은 핵심 non-agent participant를 담는다.

요청·질문·지시·촉구·제안·전달·수여처럼 **수신자가 occurrence의 핵심 participant인 경우**, 별도 RECIPIENT role이 없는 현재 ontology에서는 수신자를 TARGET으로 기록할 수 있다.

예:

- `A가 B에게 질문했다` → B는 TARGET 가능
- `A가 사법부에 차단을 촉구했다` → 사법부는 TARGET 가능
- `A에게 공로패가 수여됐다` → 수여물과 수신자 모두 semantic TARGET이 될 수 있음

다만 단순히 문장에 `에게`가 있다는 이유만으로 TARGET을 추가하지 않는다. occurrence의 semantic participant인지 확인한다.

SOURCE/GIVER, BENEFICIARY, EXPERIENCER, DESTINATION 등 별도 role이 없는 의미를 ACTOR나 PLACE에 억지로 넣지 않는다.
현재 네 role 중 TARGET의 핵심 non-agent participant 정의에 실제로 포함될 때만 TARGET으로 사용하고, 그렇지 않으면 filler 없음 또는 UNRESOLVED를 유지한다.

### PLACE

실제 occurrence의 spatial grounding. 같은 문장의 Location/기사 주제 지역/기관명 내부 지명/비교 지역/보도 dateline은 자동 PLACE가 아니다.
raw spatial phrase를 먼저 기록하고 그 뒤 Entity resolution을 검토한다.

PLACE는 물리적·지리적으로 occurrence를 grounding하는 공간이다.

다음 표현은 그 자체만으로 PLACE가 아니다.

- SNS·앱·웹사이트·온라인 채널
- 학술지·언론 매체
- 주식시장·거래소 같은 제도적 장
- 소프트웨어 실행 환경·클라우드·기술 플랫폼
- 산업 분야·사업 분야
- 이적의 출발/도착 조직
- 수신 기관
- 신체 부위·세포·조직처럼 participant 내부의 생물학적 구획

예: `X에 글을 올렸다`, `Cell에 논문이 실렸다`, `나스닥에 상장했다`, `KIA에서 NC로 이적했다`의 `X`, `Cell`, `나스닥`, 구단명은 표현만으로 PLACE가 되지 않는다.

반대로 기관명이 실제 행위의 물리적 수행 장소를 지시하는 경우에는 PLACE가 될 수 있다.
예: `서울아산병원에서 임상을 진행했다`에서 병원이 실제 임상 수행 장소로 쓰였다면 PLACE를 허용한다.

조사 `에/에서`만으로 PLACE를 결정하지 않는다.

### 공통 span/resolution/context

원문 participant/theme의 의미를 충분히 식별하는 span을 사용한다. 단순히 기존 Head가 처리할 폭으로 줄이지 않는다.
명백한 복수 filler는 각각 보존한다. 동일 surface라도 서로 다른 identity일 수 있으며 alias는 문자열이 달라도 동일할 수 있다.
허용 resolution은 `ENTITY_RESOLVED`, `SPAN_ONLY`, `VALUE_RESOLVED`, `CONTEXTUAL`, `UNRESOLVED`다.
SPAN_ONLY는 실패/negative가 아니라 명확한 textual filler이며 fake Entity로 바꾸지 않는다.

evidence_scope는 canonical enum을 유지한다: EVENT_SPAN / SAME_SENTENCE_SHARED / PREVIOUS_SENTENCE_CONTEXT / OTHER_CONTEXT.
직전 문장 inheritance는 명시 antecedent·담화 연속성·경쟁 후보 부재·모순 부재가 확인될 때만 허용한다.
다른 문장에 있는 evidence를 현재 문장 안으로 복제하지 않는다. 경쟁 antecedent가 남으면 UNRESOLVED다.

## 5. Role status와 coverage

`completeness.actor_status/target_status/place_status/time_status`:

- PRESENT: 확정한 textual/contextual filler가 있다.
- ABSENT: 본문과 문맥에서 그 역할/grounding을 도입하지 않는다.
- UNRESOLVED: role의 존재/범위/identity를 충분히 정할 수 없다.

`completeness.actor_coverage/target_coverage/place_coverage/time_coverage`:

- EXHAUSTIVE: 기사 전체 문맥과 Event를 실제로 읽고 해당 role의 모든 semantic filler를 검토했으며 현재 목록이 완전하다고 판정했다.
- PARTIAL: 적어도 한 확정 filler는 있지만 목록의 완전성을 보장할 수 없다.
- UNRESOLVED: role 존재/범위/identity 자체에 해결되지 않은 문제가 있다.
- NOT_REVIEWED: 유효한 검토가 완료되지 않았다.

frame_reviewed=true, parent confidence, 빈 배열, 같은 round의 다른 Event, 반복된 reason을 근거로 coverage를 자동 결정하지 않는다.
보류된 proposition/identity 때문에 role set을 확정할 수 없으면 coverage도 보수적으로 남긴다.

### Safe supervision

- PRESENT + EXHAUSTIVE: 목록은 complete positive set이다. 명시적으로 선언된 evaluation/candidate scope 내에서 나머지 후보는 **해당 role의** negative가 될 수 있다.
- ABSENT + EXHAUSTIVE: filler0. 같은 scope 후보는 해당 role negative가 될 수 있다.
- PRESENT + PARTIAL: 확정 filler만 positive, unspecified 후보는 UNKNOWN이다.
- UNRESOLVED 또는 NOT_REVIEWED: unmatched 후보 negative 생성 금지.
- uncertainty/HUMAN_REVIEW_REQUIRED가 있는 filler/영향 범위는 확정 supervision에서 제외한다.

EXHAUSTIVE는 semantic filler 목록 보증이지 본문 내 모든 가능한 별칭 span/동일 개체 mention/동등한 span 경계를 별도 filler로 모두 열거했다는 뜻이 아니다.
downstream는 candidate scope, canonical evidence boundary/equivalence, resolution/coreference 영향, 겹치는 미해결 evidence를 선언해야 한다. 같은 participant의 확정 동치 표현을 단지 offset이 다르다는 이유로 semantic negative라고 주장해서는 안 된다.

## 6. Generic TimeExpression 계약과 보존

③ textual TimeExpression span, ⑤ Event→TimeExpression TIME attachment, ⑧ service normalization/precision/interval은 서로 다른 책임이다.
Construction Gold의 neural truth는 generic textual time이다. DATE/TIME/DURATION/SET을 필수/diagnostic Gold subtype으로 추가하지 않는다.
publishedAt anchor나 normalization fallback은 파생 정보이며 모델이 맞힌 원문 발생시간이 아니다. subtype과 normalized value도 서로 다르다.

원문 TIME 자체를 재분류/삭제하거나 metadata 시간을 보충하지 않는다.
변경되지 않은 proposition에서 누락/오부착 의심을 발견하면 제안/review queue에 기록하고, 이를 고친 것처럼 EXHAUSTIVE를 찍지 않는다.

## 7. Narrow ABOUT: 다른 명시적 proposition에 대한 직접 참조

ABOUT은 Statement가 **다른 독립 Event 또는 Statement**를 평가·논평·반박·예측·주장의 대상으로 직접 참조하는 관계다.
방향은 `SOURCE_STATEMENT → TARGET_EVENT|TARGET_STATEMENT`다.
허용 target은 현재 annotation inventory에 존재하는 EVENT 또는 STATEMENT ID뿐이다.

허용 예:

- 이미 annotation된 금리 인상 Event에 대해 “정부의 금리 인상은 잘못된 결정이다”라고 평가하는 Statement.
- 이미 존재하는 A의 전망 Statement를 “그 전망은 지나치게 낙관적”이라고 논평하는 별도 Statement.

허용하지 않음:

- Entity topic (`삼성전자`를 언급했다는 이유), concept/topic/일반 사물
- Statement 자신의 content, 자기 자신 ID
- raw clause, lexical overlap, 같은 기사 주제라는 이유
- 단순 reporting/attribution frame 자체
- 미래 계획의 내용만으로 별도의 실제 Event를 만들어 연결
- 단순 배경, 원인, 결과, 시간적 선후, 같은 담화 흐름이라는 이유

모든 Statement를 본문 문맥과 안정된 proposition 목록으로 읽는다. broad ABOUT나 legacy endpoint를 새 endpoint의 기계적 seed로 쓰지 않는다.
다른 proposition을 직접 지시하는 근거가 없으면 ABOUT 없음이 올바른 판정일 수 있다. 모든 Statement에 ABOUT를 강제하지 않는다.
target이 실제 본문에 있으나 기존 annotation inventory에 없으면 ABOUT를 위해 fake node를 만들지 않는다. 독립 proposition 누락/병합인지 proposition 단계에서 먼저 판정한다.
모호한 참조는 hard link를 확정하지 않고 review queue에 남긴다.

### ABOUT supervision 권한

canonical Gold의 `about_status=NONE` 또는 `about_negative_policy=NOT_AUTHORIZED`는 **unlinked pair 전체를 negative로 승인한다는 뜻이 아니다**.

- 확정 ABOUT link → POSITIVE
- 별도 review에서 특정 source-target exact pair를 `REVIEWED_NON_LINK`로 확정 → 그 exact pair에 한해 `SAFE_NEGATIVE_PAIR`
- AMBIGUOUS / UPSTREAM_REVIEW_REQUIRED → UNKNOWN
- 검수되지 않은 unlinked pair → UNKNOWN

`SAFE_NEGATIVE_PAIR`는 pair-local authority다. 같은 source의 다른 target, 같은 target의 다른 source, 같은 article의 다른 unlinked pair로 일반화하지 않는다.
reviewed pair-local negative는 sidecar/review artifact에 둘 수 있으며, 기존 RC1 schema의 canonical Gold row를 억지로 확장하지 않는다.

## 8. Hard Relations

CAUSES와 SUBEVENT_OF는 Event↔Event directed relation이다. 둘 다 EventCoref와 독립이며 relation 결과를 occurrence identity에 피드백하지 않는다.
canonical `hard_relations`는 확정 positive relation을 표현한다. **관계가 기록되어 있지 않다는 사실만으로 negative를 만들지 않는다.**

### 8.1 공통 원칙

- source와 target은 모두 annotation inventory에 존재하는 실제 EVENT여야 한다.
- self-edge는 금지한다.
- retired/fake/missing endpoint를 relation 때문에 되살리지 않는다.
- 같은 actor, 장소, 시간, 문장, lexical overlap, 기사 topic만으로 relation을 만들지 않는다.
- direct relation만 annotation한다. transitive closure를 자동 생성하지 않는다.
- 방향을 바꾸면 다른 relation이 된다. source/target을 대칭 취급하지 않는다.
- 근거가 competing interpretation에 의존하면 hard link 대신 UNKNOWN/review queue로 남긴다.

### 8.2 CAUSES

CAUSES는 한 실제 Event occurrence가 다른 실제 Event occurrence의 발생/변화를 **원인으로 직접 유발했다고 기사 문맥이 제시하는 관계**다.
방향은 항상:

`CAUSE_EVENT → EFFECT_EVENT`

허용:

- 본문이 원인과 결과를 명시적으로 연결한다: `A로 인해 B가 발생했다`, `A 때문에 B가 감소했다`.
- 문장 간이라도 discourse/context를 읽었을 때 특정 cause Event와 특정 effect Event 사이의 직접 인과가 명확하다.

허용하지 않음:

- 단순 시간적 선후 (`A 후 B`)
- 상관·동시 발생·같은 추세
- 같은 actor/target/location을 공유함
- 하나가 다른 하나의 배경이라는 이유만 있음
- 단순 prerequisite/enabling condition이지만 기사에서 직접 causal relation을 제시하지 않음
- ABOUT 관계와 같은 평가/논평 관계
- SUBEVENT_OF의 구성 관계
- A→B, B→C만 근거로 A→C를 자동 생성

기사에 “A가 B의 원인이라고 주장했다/분석했다/전망했다”는 Statement만 있고 causal relation 자체가 기사-local factual relation으로 확정되지 않으면, 그 epistemic status를 무시해 hard CAUSES를 만들지 않는다. Statement와 ABOUT/Assertor를 보존한다.

#### Causal discourse marker 판정

연결어미·담화표지 자체는 CAUSES의 충분조건이 아니다.

다음 표현만으로 hard CAUSES를 만들지 않는다.

- `-며`, `-면서`
- `-자`
- `-다가`
- `-고`
- `A 후 B`, `A 이후 B`
- `그 결과`
- `계기로`
- `후속 조치로`

이 표현들은 동시성·시간적 선후·계기·절차적 연결도 나타낼 수 있다.

CAUSES를 확정하려면 표면 연결어와 별개로 기사 문맥이 특정 cause Event가 특정 effect Event의 발생·변화를 직접 유발했다고 제시해야 한다.

실험 기사에서 `A를 처치한 그룹에서 B가 나타났다`라는 군별 대응 관측만 있는 경우도 자동으로 CAUSES가 아니다. 기사 문맥이 A→B의 직접 causal interpretation을 실제로 제시하는지 별도로 판정한다.

`그 결과`의 antecedent가 여러 Event 전체이거나 cause endpoint 하나를 확정할 수 없으면 임의의 대표 Event를 고르지 않는다.

### 8.3 SUBEVENT_OF

SUBEVENT_OF는 서로 다른 두 실제 Event occurrence 중 child가 **명시적으로 구획 가능한 bounded parent episode를 구성하는 실제 단계·행위·국면**인 관계다.
방향은 항상:

`CHILD_EVENT → BOUNDED_PARENT_EVENT`

필수 조건:

1. child와 parent는 서로 다른 occurrence다. 같은 occurrence의 재언급이면 EventCoref MERGE다.
2. parent는 기사 안에 독립 Event proposition으로 존재해야 한다.
3. parent는 bounded episode여야 한다. 시작/종료 또는 episode 경계를 기사 문맥에서 구별할 수 있어야 한다.
4. child는 parent의 실제 constituent occurrence여야 한다. 단순히 같은 시기·장소·주제를 공유하는 별도 사건이면 안 된다.
5. parent가 둘 이상 경쟁하거나 boundedness가 불분명하면 hard link를 확정하지 않는다.

boundedness는 명시적인 종료 날짜·시각이 반드시 존재해야 한다는 뜻이 아니다.

기사 문맥에서 다음과 같은 유한한 semantic boundary를 구별할 수 있으면 진행 중인 parent도 bounded episode가 될 수 있다.

- 명시된 시작과 종료
- 특정 회의·경기·행사·공판·작전처럼 본질적으로 구획된 episode
- 명시된 목표나 완료 조건을 가진 특정 실행 절차
- 시작이 확인되고 기사 안에서 구성 단계와 완료 조건이 한정되는 특정 작업

반대로 다음은 bounded parent로 사용하지 않는다.

- `수년간 대응해 왔다`
- `사업을 추진하고 있다`
- `연구에 몰두하고 있다`
- `관심이 이어지고 있다`

처럼 종료·완료 조건 없이 열린 상태·경향·정책 흐름만을 나타내는 Event.

child가 parent 시간 범위 안에 있다는 사실만으로 SUBEVENT_OF가 되는 것은 아니다. child가 그 parent episode를 실제로 구성하는 단계·행위·국면이어야 한다.

bounded parent의 전형적 예:

- 특정 회의/정상회담/공판/경기/행사/작전/협상/시위/수사 episode
- 기사에서 하나의 독립 occurrence로 명시된 절차·프로그램의 특정 실행 episode

그 자체만으로 parent가 되지 않는 것:

- `경제 위기`, `AI 산업 발전`, `정부 정책`, `시장 상황`처럼 열린 상태·주제
- 기사 전체의 topic이나 background
- 단지 같은 actor가 수행한 여러 Event
- 시간적으로 가까운 Event
- CAUSES/precondition/result 관계일 뿐 구성 관계가 아닌 Event

예:

- `비공개 회담`이 기사에 명시된 `정상회담`의 실제 구성 단계라면 `비공개 회담 → 정상회담`.
- `폭우`가 `도로 통제`를 유발했다면 CAUSES일 수 있지만 SUBEVENT_OF는 아니다.
- 동일한 `정상회담`을 기사 앞뒤에서 다시 언급한 두 span은 SUBEVENT_OF가 아니라 EventCoref 대상이다.

SUBEVENT_OF도 direct constituent edge만 annotation한다. `A → B`, `B → C`가 있다고 `A → C`를 자동 추가하지 않는다.
cycle과 self-edge는 금지한다.

### 8.4 Hard relation supervision 권한

- canonical positive CAUSES/SUBEVENT_OF → POSITIVE
- 별도 review에서 특정 directed Event pair를 해당 relation이 아니라고 확정 → 그 exact directed pair에 한해 `SAFE_NEGATIVE_PAIR`
- AMBIGUOUS / UPSTREAM_REVIEW_REQUIRED / endpoint uncertainty → UNKNOWN
- 검수되지 않은 unlinked Event pair → UNKNOWN

relation별 negative 권한은 독립이다. 예를 들어 `(A,B)`가 `SUBEVENT_OF`의 safe negative라고 해서 자동으로 `CAUSES` negative가 되는 것은 아니다.
reviewed exact-pair negative는 sidecar/review artifact에 저장할 수 있으며, canonical Gold의 positive-only `hard_relations` 구조를 closed-world negative table로 해석하지 않는다.

### 8.5 관계 혼동 방지

| 상황 | 판정 |
|---|---|
| 같은 occurrence의 재언급 | EventCoref MERGE |
| Event A가 Event B를 직접 유발 | `A CAUSES B` |
| Event A가 bounded Event B의 구성 단계 | `A SUBEVENT_OF B` |
| Statement가 다른 Event/Statement를 평가·논평·반박·예측 | `Statement ABOUT target` |
| 같은 topic/actor/time/location일 뿐 | hard relation 없음 |
| 판단 근거가 불충분하거나 endpoint 자체가 불안정 | UNKNOWN / review queue |

## 9. Entity identity와 영향 전파

PERSON/ORGANIZATION/LOCATION/PRODUCT ontology를 유지한다. valid nested mention을 flat BIO 때문에 삭제하지 않는다.

### 9.1 네 Entity type의 적용 범위

고유명·식별 가능한 표현이라는 이유만으로 반드시 네 Entity type 중 하나를 부여하지 않는다.

현재 ontology에 의미적으로 맞는 type이 없으면 EntityMention을 만들지 않고 필요한 Event role/Assertor에서는 raw span을 `SPAN_ONLY`로 보존할 수 있다.

#### PERSON

실제 개인 또는 기사 안에서 특정 개인을 안정적으로 지시하는 표현.

#### ORGANIZATION

회사·기관·정부기관·학교·정당·팀 등 조직적 행위 주체로 존재하는 실체.

#### LOCATION

국가·지역·도시·시설 등 지리적·공간적 장소 실체.

#### PRODUCT

사람·조직·장소가 아니면서 제작·발행·개발된 artifact, instrument, software/service 또는 named content로 article-local identity를 갖는 대상.

PRODUCT에 포함 가능:

- 기기·차량·제품·의약품
- 소프트웨어·앱·디지털 서비스
- 금융상품·시장지수
- 책·논문·앨범·곡·사진 작품·방송 프로그램 등 named content

기본적으로 PRODUCT로 만들지 않음:

- 경기·대회·행사 자체
- 정책·사업·프로젝트라는 활동 자체
- 바이러스 계통·생물종
- 일반 기술·품목·물질 범주
- 추상 개념
- 직위·역할명
- 단순 절차·방법명

예를 들어 `WBC`, `르망 24시간` 같은 대회나 `H5N1` 같은 바이러스 계통을 네 type 중 하나에 억지로 넣지 않는다.

Entity가 없더라도 Event role의 명확한 textual filler를 삭제하지 않는다.

### 9.2 동일 surface의 metonymy와 referent 분리

Entity type은 문자열 자체가 아니라 해당 mention이 article-local하게 지시하는 referent를 기준으로 판정한다.

같은 surface가 서로 다른 실체를 지시하면 하나의 LocalEntity로 강제 병합하지 않는다.

예:

- `디스코드가 행정심판을 청구했다` → 회사/운영 주체라면 ORGANIZATION
- `디스코드에서 영상을 봤다` → 서비스 자체라면 PRODUCT
- `미국이 발표했다` → 정부·국가 행위 주체에 대한 환유
- `미국에서 개최됐다` → LOCATION

국가명·플랫폼명·기관명 등에서 환유가 발생했다고 surface type을 전역적으로 바꾸지 않는다.
article-local 문맥에서 referent가 실제로 다르면 mention identity/type을 분리하고, 문맥만으로 확정할 수 없으면 UNRESOLVED로 남긴다.

외부 지식을 사용해 동일성을 강제하지 않는다.

실제 artifact가 확정될 때만 mention/cluster를 수정한다. 잘못된 identity resolution이면 영향을 받는 role/assertor reference를 재검토하며 단순 문자열 일치로 redirect하지 않는다.

Proposition lineage는 기존 identity 유지 시 retained ID를 보존한다. 실제 분할이면 old→split_into new IDs를 기록하고 부모를 재사용해 서로 다른 occurrence를 혼합하지 않는다.
Event 변경: Trigger·네 role·EventCoref·CAUSES/SUBEVENT_OF·ABOUT target·evidence를 영향 범위에서 검토한다.
Statement 변경: Type·Assertor·ABOUT source/target·evidence를 검토한다.
split된 Event 역할/Statement Assertor를 자동 복사하지 않는다.

같은 occurrence는 EventCoref MERGE, 다른 occurrence의 명시적 구성 관계는 SUBEVENT_OF(child,parent)다.
RESPONDS_TO는 현재 계약에 포함하지 않는다.
## 10. 제출 및 검증

모든 text span은 processed content 기준 Unicode code point, 0-based, end-exclusive이며 slice와 text가 exact하게 같아야 한다.

검사 항목:

- ID/reference/cluster membership
- ABOUT target kind와 self-link
- CAUSES/SUBEVENT_OF source-target 방향
- hard relation self-edge
- SUBEVENT_OF cycle
- retired lineage
- fake/dangling endpoint
- reviewed pair-local negative가 다른 pair로 일반화되지 않았는지
- UNKNOWN이 loss용 negative로 변환되지 않았는지

EXHAUSTIVE+PRESENT는 filler≥1, EXHAUSTIVE+ABSENT는 filler0이며 unresolved/PARTIAL/NOT_REVIEWED를 negative로 내보내지 않는다.
schema 통과는 의미 검토의 대체물이 아니다. review artifact coverage와 source guideline revision/SHA를 별도로 검증한다.
불확실성은 HUMAN_REVIEW_REQUIRED 또는 동등한 review queue 상태로 노출한다.

## 11. RC1 compatibility note

기존 RC1 schema의 구조 계약은 변경하지 않는다.

guideline version 필드는 backward-compatible enum으로 다음 값을 허용한다.

- `annotation_guideline_version`:
  - `v3-guideline-r02-curated-rc1`
  - `v3-guideline-r03`
  - `v3-guideline-r04`

- curation review의 `guideline_version`:
  - `v3-guideline-r02-curated-rc1`
  - `v3-guideline-r03`
  - `v3-guideline-r04`

기존 Gold와 기존 curation/review artifact의 guideline version 및 source guideline SHA는 변경하지 않는다.
r04를 실제로 적용해 새로 adjudicate한 record만 r04를 기록한다.

이 guideline을 사용해 Gold를 새로 재발행하는 시점에는 top-level guideline version, artifact version, release identifier와 manifest를 함께 갱신한다.

이 문서의 목적은 relation마다 별도 semantic contract 문서를 계속 늘리는 대신, 이후 annotation/recovery에서 사용할 의미 계약을 하나의 통합 guideline으로 유지하는 것이다.
