// 별빛 뉴스 Neo4j 5.26 LTS 초기 그래프 스키마
// 기준: 최종 DB/ERD 설계 문서
// 역할: 고유성 제약조건, 검색 인덱스, 고정 Topic 초기화
// 모든 ZONED DATETIME 값은 Asia/Seoul 시간대를 사용한다.
// Vector Index는 임베딩 모델과 차원이 확정된 뒤 별도 Migration으로 생성한다.

// [Unique constraints]
CREATE CONSTRAINT article_node_id_unique IF NOT EXISTS
FOR (n:Article)
REQUIRE n.nodeId IS UNIQUE;

CREATE CONSTRAINT article_mysql_id_unique IF NOT EXISTS
FOR (n:Article)
REQUIRE n.mysqlArticleId IS UNIQUE;

CREATE CONSTRAINT event_node_id_unique IF NOT EXISTS
FOR (n:Event)
REQUIRE n.nodeId IS UNIQUE;

CREATE CONSTRAINT story_node_id_unique IF NOT EXISTS
FOR (n:Story)
REQUIRE n.nodeId IS UNIQUE;

CREATE CONSTRAINT topic_node_id_unique IF NOT EXISTS
FOR (n:Topic)
REQUIRE n.nodeId IS UNIQUE;

CREATE CONSTRAINT topic_code_unique IF NOT EXISTS
FOR (n:Topic)
REQUIRE n.topicCode IS UNIQUE;

CREATE CONSTRAINT entity_node_id_unique IF NOT EXISTS
FOR (n:Entity)
REQUIRE n.nodeId IS UNIQUE;

CREATE CONSTRAINT news_organization_mysql_id_unique IF NOT EXISTS
FOR (n:NewsOrganization)
REQUIRE n.mysqlOrganizationId IS UNIQUE;

CREATE CONSTRAINT time_node_id_unique IF NOT EXISTS
FOR (n:Time)
REQUIRE n.nodeId IS UNIQUE;

CREATE CONSTRAINT time_key_unique IF NOT EXISTS
FOR (n:Time)
REQUIRE n.timeKey IS UNIQUE;

CREATE CONSTRAINT statement_node_id_unique IF NOT EXISTS
FOR (n:Statement)
REQUIRE n.nodeId IS UNIQUE;

CREATE CONSTRAINT user_id_unique IF NOT EXISTS
FOR (n:User)
REQUIRE n.userId IS UNIQUE;

// [Range indexes]
CREATE RANGE INDEX article_published_at IF NOT EXISTS
FOR (n:Article)
ON (n.publishedAt);

CREATE RANGE INDEX article_subtopic_code IF NOT EXISTS
FOR (n:Article)
ON (n.subtopicCode);

CREATE RANGE INDEX event_occurred_at IF NOT EXISTS
FOR (n:Event)
ON (n.occurredAt);

CREATE RANGE INDEX story_last_event_at IF NOT EXISTS
FOR (n:Story)
ON (n.lastEventAt);

// [Full-text indexes]
CREATE FULLTEXT INDEX article_title_fulltext IF NOT EXISTS
FOR (n:Article)
ON EACH [n.title];

CREATE FULLTEXT INDEX event_fulltext IF NOT EXISTS
FOR (n:Event)
ON EACH [n.title, n.aliases];

CREATE FULLTEXT INDEX story_title_fulltext IF NOT EXISTS
FOR (n:Story)
ON EACH [n.title];

CREATE FULLTEXT INDEX entity_fulltext IF NOT EXISTS
FOR (n:Entity)
ON EACH [n.canonicalName, n.aliases];

CREATE FULLTEXT INDEX statement_text_fulltext IF NOT EXISTS
FOR (n:Statement)
ON EACH [n.text];

// [Fixed Topic seed]
WITH datetime({timezone: 'Asia/Seoul'}) AS now
UNWIND [
    {topicCode: 'POLITICS', nameKo: '정치', displayOrder: 1},
    {topicCode: 'ECONOMY', nameKo: '경제', displayOrder: 2},
    {topicCode: 'SOCIETY', nameKo: '사회', displayOrder: 3},
    {topicCode: 'CULTURE', nameKo: '문화', displayOrder: 4},
    {topicCode: 'INTERNATIONAL', nameKo: '국제', displayOrder: 5},
    {topicCode: 'SPORTS', nameKo: '스포츠', displayOrder: 6},
    {topicCode: 'IT_SCIENCE', nameKo: 'IT·과학', displayOrder: 7}
] AS topic
MERGE (n:Topic {topicCode: topic.topicCode})
ON CREATE SET
    n.nodeId = randomUUID(),
    n.createdAt = now
SET
    n.nodeId = coalesce(n.nodeId, randomUUID()),
    n.createdAt = coalesce(n.createdAt, now),
    n.nameKo = topic.nameKo,
    n.displayOrder = topic.displayOrder,
    n.isActive = true,
    n.updatedAt = now;

// [Application-enforced graph rules]
// - 같은 시작 노드·관계 타입·도착 노드 조합은 MERGE로 하나만 저장한다.
// - Neo4j에 저장된 Article은 COVERS 관계를 하나 이상 가져야 한다.
// - Article별 isPrimary=true인 COVERS 관계는 정확히 하나만 허용한다.
// - Article·Event·Story별 isPrimary=true인 CLASSIFIED_AS 관계는 최대 하나만 허용한다.
// - CAUSES, SUBEVENT_OF, BACKGROUND_OF, RELATED_TO 자기 참조를 금지한다.
// - SUBEVENT_OF 순환 관계를 금지한다.
// - confidence, relevance, similarityScore, score, coverageRate는 0~1 범위로 검증한다.
// - CONSUMED 집계값은 증분이 아닌 절대 누적값으로 덮어쓴다.
// - entityType에 따라 Entity와 세부 Label을 함께 부여한다.
// - granularity에 따라 Time과 Year, Month 또는 Day Label을 함께 부여한다.
// - 이미 별도 노드로 저장된 Event끼리의 사후 병합은 현재 범위에서 수행하지 않는다.

// [Vector index migration note]
// 임베딩 차원과 유사도 함수가 확정되면 Article, Event, Story, Entity, Statement 중
// 실제 검색·추천에 사용하는 Label에 대해 CREATE VECTOR INDEX Migration을 추가한다.
