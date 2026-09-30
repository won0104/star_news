/**
 * 지식 그래프 코드의 화면 이름 — 한 곳에서만 관리한다.
 *
 * 백엔드는 Neo4j 의 코드를 그대로 보낸다: 관계는 `type(r)`(ACTOR, PLACE …), 노드 유형은
 * nodeType(EVENT …), 개체·발언의 세부 유형은 entityType / statementType(PERSON, COMPANY …).
 * 한글로 옮기는 일은 화면의 몫이라, 트렌드 별자리·나의 기록 행성·검색·저장한 사건이 모두
 * 여기서 가져간다. 전에는 표가 네 군데에 따로 있어 같은 관계가 "발언"과 "발언 포함"으로
 * 갈렸고, 새 코드(PLACE 등)가 어느 표에도 없어 영문 그대로 나왔다.
 *
 * 없는 코드는 쓰는 쪽에서 원문을 그대로 보여준다(`labels[code] ?? code`). 새 코드가 생기면
 * 이 파일에만 더한다. 코드 목록의 근거는 ai/starlight_ai/adapter/neo4j_schema.py
 * (PUBLIC_EDGE_TYPES, ENTITY_TYPE_LABEL)와 배포 Neo4j 의 관계 종류(2026-09-27 조회)다.
 */

/** 관계 이름. 별 아래 작은 글씨와 "→ 주체 · 이름" 목록에 함께 쓰여 짧게 둔다. */
export const edgeLabels = {
  // 사건 → 개체
  ACTOR: '주체',
  TARGET: '대상',
  PLACE: '장소',
  // 사건 → 시점. DB 이름은 OCCURRED_ON 이다. OCCURRED_AT 은 목업(trendNeighbors.js)이 쓰던 이름이라 남긴다.
  OCCURRED_ON: '시점',
  OCCURRED_AT: '시점',
  // 사건 ↔ 사건
  // 인과를 단정하지 않는다 — 추출된 관계가 꼭 원인과 결과인 것은 아니어서 넓은 이름으로 둔다.
  CAUSES: '관련 사건',
  SUBEVENT_OF: '상위 사건',
  // 사건 → Story, 시점 → 상위 시점. 사건 쪽 뜻(더 큰 흐름에 속함)에 맞춘 이름이다.
  PART_OF: '상위 흐름',
  // 발언
  ABOUT: '관련 발언',
  ASSERTED_BY: '발언자',
  CONTAINS_STATEMENT: '발언',
  // 기사 → 노드
  COVERS: '보도',
  MENTIONS: '언급',
  // 분야
  CLASSIFIED_AS: '분야',
  BELONGS_TO_TOPIC: '분야',
}

/** 노드 유형. 개체는 사람·회사·장소를 모두 담아 "인물·기관"으로 부른다. */
export const nodeTypeLabels = {
  EVENT: '사건',
  ENTITY: '인물·기관',
  STATEMENT: '발언',
  TIME: '시점',
}

/** 개체·발언의 세부 유형. 모르는 값은 원문 그대로 보여준다. */
export const subtypeLabels = {
  // 개체 (entityType)
  PERSON: '인물',
  ORGANIZATION: '기관·기업',
  COMPANY: '회사',
  GOVERNMENT_AGENCY: '정부·공공기관',
  NEWS_ORGANIZATION: '언론사',
  LOCATION: '장소',
  PRODUCT: '제품',
  POLICY: '정책·제도',
  INDICATOR: '지표',
  // 발언 (statementType)
  PLAN: '계획·발표',
  ASSESSMENT: '평가·전망',
  FACT: '사실',
}
