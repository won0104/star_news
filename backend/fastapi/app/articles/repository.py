# 기사 분석 도메인의 Neo4j 쿼리 (Node/Edge 생성·조회).
import math
from datetime import datetime

from neo4j import ManagedTransaction, Session

from app.articles.support.entity_filter import is_noise_entity_name, normalize_entity_name

# 기사 분석 파이프라인 중간에 실패하면 그 전까지 만든 노드가 남지 않도록, 이 파일의 함수들을 전부 트랜잭션 하나로 묶어서 호출
Neo4jRunner = Session | ManagedTransaction

# Event dedup 벡터 유사도 임계값
EVENT_SIMILARITY_THRESHOLD = 0.92
# 벡터 검색 시 후보로 가져올 최대 개수
EVENT_CANDIDATE_TOP_K = 8
# 대표 벡터(centroid) 갱신 시 새 임베딩을 반영하는 비율 (지수이동평균)
EVENT_EMBEDDING_EMA_WEIGHT = 0.15

# 1. Article
# Article 노드를 생성하거나 이미 있으면 갱신한다
def merge_article_node(
    session: Neo4jRunner,
    mysql_article_id: int,
    title: str,
    published_at: datetime,
    subtopic_code: str | None,
    analyzed_at: datetime,
) -> str:
    result = session.run(
        """
        // mysqlArticleId(자연키)로 MERGE - 동일 articleId 재요청해도 중복 노드 안 생김 (멱등)
        MERGE (a:Article {mysqlArticleId: $mysqlArticleId})
        ON CREATE SET a.nodeId = randomUUID(), a.createdAt = $analyzedAt
        SET a.title = $title,
            a.publishedAt = $publishedAt,
            a.subtopicCode = $subtopicCode,
            a.analyzedAt = $analyzedAt,
            a.updatedAt = $analyzedAt
        RETURN a.nodeId AS nodeId
        """,
        mysqlArticleId=mysql_article_id,
        title=title,
        publishedAt=published_at,
        subtopicCode=subtopic_code,
        analyzedAt=analyzed_at,
    ).single()
    return result["nodeId"]


# Year 노드를 생성하거나 갱신한다.
def _merge_year_node(session: Neo4jRunner, year: str, created_at: datetime) -> str:
    result = session.run(
        """
        // timeKey는 "YYYY"
        MERGE (y:Time:Year {timeKey: $year})
        ON CREATE SET y.nodeId = randomUUID(), y.createdAt = $createdAt
        SET y.value = $year, y.granularity = 'YEAR', y.year = toInteger($year)
        RETURN y.nodeId AS nodeId
        """,
        year=year,
        createdAt=created_at,
    ).single()
    return result["nodeId"]


# Month 노드를 생성하거나 갱신하고 Year에 연결한다.
def _merge_month_node(session: Neo4jRunner, month_key: str, year: str, created_at: datetime) -> str:
    result = session.run(
        """
        // timeKey는 "YYYY-MM"
        MATCH (y:Time:Year {timeKey: $year})
        MERGE (m:Time:Month {timeKey: $monthKey})
        ON CREATE SET m.nodeId = randomUUID(), m.createdAt = $createdAt
        SET m.value = $monthKey, m.granularity = 'MONTH',
            m.year = toInteger($year), m.month = toInteger(split($monthKey, '-')[1])
        MERGE (m)-[:PART_OF]->(y)
        RETURN m.nodeId AS nodeId
        """,
        monthKey=month_key,
        year=year,
        createdAt=created_at,
    ).single()
    return result["nodeId"]


# Day 노드를 생성하거나 갱신하고 Month에 연결한다.
def _merge_day_node(session: Neo4jRunner, day_key: str, month_key: str, created_at: datetime) -> str:
    year, month, day = day_key.split("-")
    result = session.run(
        """
        // timeKey는 "YYYY-MM-DD"
        MATCH (m:Time:Month {timeKey: $monthKey})
        MERGE (d:Time:Day {timeKey: $dayKey})
        ON CREATE SET d.nodeId = randomUUID(), d.createdAt = $createdAt
        SET d.value = $dayKey, d.granularity = 'DAY',
            d.year = toInteger($year), d.month = toInteger($month), d.day = toInteger($day)
        MERGE (d)-[:PART_OF]->(m)
        RETURN d.nodeId AS nodeId
        """,
        dayKey=day_key,
        monthKey=month_key,
        year=year,
        month=month,
        day=day,
        createdAt=created_at,
    ).single()
    return result["nodeId"]

# 2. Time
# 모델에서 반환된 Time 하나(Year/Month/Day 중 하나의 granularity)를 반영하고, 그 nodeId를 반환한다.
def merge_time_node(session: Neo4jRunner, time_key: str, granularity: str, created_at: datetime) -> str:
    # Day/Month/Year 계층(PART_OF)은 항상 끝까지 같이 보장한다
    # (예: DAY가 오면 Day/Month/Year 3개 노드 + PART_OF 2개를 다 만듦). time_key: "YYYY"/"YYYY-MM"/"YYYY-MM-DD"
    year = time_key[:4]
    year_node_id = _merge_year_node(session, year, created_at)
    if granularity == "YEAR":
        return year_node_id

    month_key = time_key[:7]
    month_node_id = _merge_month_node(session, month_key, year, created_at)
    if granularity == "MONTH":
        return month_node_id

    return _merge_day_node(session, time_key, month_key, created_at)

# 3. Entity
# 언론사(NewsOrganization) Entity를 생성하거나 갱신
def merge_news_organization_entity(
    session: Neo4jRunner, mysql_organization_id: int, name: str, created_at: datetime
) -> str:
    result = session.run(
        """
        // mysqlOrganizationId(자연키)로 MERGE
        MERGE (o:Entity:NewsOrganization {mysqlOrganizationId: $mysqlOrganizationId})
        ON CREATE SET o.nodeId = randomUUID(), o.createdAt = $createdAt
        SET o.canonicalName = $name,
            o.entityType = 'NEWS_ORGANIZATION',
            o.updatedAt = $createdAt
        RETURN o.nodeId AS nodeId
        """,
        mysqlOrganizationId=mysql_organization_id,
        name=name,
        createdAt=created_at,
    ).single()
    return result["nodeId"]


# 기사 본문에서 뽑은 Entity를 생성하거나 이미 있으면 재사용
def merge_extracted_entity(
    session: Neo4jRunner, canonical_name: str, entity_type: str, created_at: datetime
) -> str | None:

    # 노이즈면 None
    normalized_name = normalize_entity_name(canonical_name)
    if is_noise_entity_name(normalized_name):
        return None

    result = session.run(
        """
        // canonicalName(정규화된 이름)으로 MERGE - 다른 기사에서 같은 이름이면 재사용, 다르면 새로 생성
        MERGE (e:Entity {canonicalName: $canonicalName})
        ON CREATE SET e.nodeId = randomUUID(), e.createdAt = $createdAt
        // entityType은 처음 값으로 고정(coalesce)
        SET e.entityType = coalesce(e.entityType, $entityType), e.updatedAt = $createdAt
        FOREACH (_ IN CASE WHEN e.entityType = 'PERSON' THEN [1] ELSE [] END | SET e:Person)
        FOREACH (_ IN CASE WHEN e.entityType = 'LOCATION' THEN [1] ELSE [] END | SET e:Location)
        FOREACH (_ IN CASE WHEN e.entityType = 'ORGANIZATION' THEN [1] ELSE [] END | SET e:Organization)
        RETURN e.nodeId AS nodeId
        """,
        canonicalName=normalized_name,
        entityType=entity_type,
        createdAt=created_at,
    ).single()
    return result["nodeId"]

# 4. Event
# 벡터 유사도가 높아도 병합하면 안 되는 "하드 충돌"인지 판단.
# - 둘 다 Actor가 2명 이상인데 겹치는 사람이 없음  
# - 둘 다 Target이 있는데 겹치는 대상이 없음
def _has_event_conflict(
    candidate_actor_names: list[str],
    candidate_target_names: list[str],
    new_actor_names: list[str],
    new_target_names: list[str],
) -> bool:
    if len(candidate_actor_names) >= 2 and len(new_actor_names) >= 2:
        if set(candidate_actor_names).isdisjoint(new_actor_names):
            return True

    if candidate_target_names and new_target_names:
        if set(candidate_target_names).isdisjoint(new_target_names):
            return True

    return False


# 기존 Event 후보 하나의 dedup 판단 재료(임베딩/Actor/Target)를 한 번에 조회
def _fetch_event_dedup_signals(session: Neo4jRunner, event_node_id: str) -> dict:
    result = session.run(
        """
        MATCH (e:Event {nodeId: $nodeId})
        OPTIONAL MATCH (e)-[:ACTOR]->(actor:Entity)
        OPTIONAL MATCH (e)-[:TARGET]->(target:Entity)
        RETURN e.embedding AS embedding,
               collect(DISTINCT actor.canonicalName) AS actorNames,
               collect(DISTINCT target.canonicalName) AS targetNames
        """,
        nodeId=event_node_id,
    ).single()
    return {
        "embedding": result["embedding"],
        "actorNames": list(result["actorNames"]),
        "targetNames": list(result["targetNames"]),
    }


# 대표 벡터(centroid) 갱신 - 지수이동평균으로 기존 임베딩에 새 임베딩을 소량 반영 후 재정규화
def _ema_update_embedding(old_embedding: list[float], new_embedding: list[float], weight: float) -> list[float]:
    blended = [old * (1 - weight) + new * weight for old, new in zip(old_embedding, new_embedding)]
    norm = math.sqrt(sum(v * v for v in blended))
    if norm == 0:
        return blended
    return [v / norm for v in blended]


# 매칭된 기존 Event를 갱신 - 임베딩은 이미 EMA로 섞인 값을 받고, 제목은 새로운 표현이면 aliases에 추가
def _update_matched_event(session: Neo4jRunner, node_id: str, title: str, blended_embedding: list[float], updated_at: datetime) -> str:
    result = session.run(
        """
        MATCH (e:Event {nodeId: $nodeId})
        SET e.embedding = $embedding, e.updatedAt = $updatedAt,
            e.aliases = CASE WHEN $title IN coalesce(e.aliases, []) OR $title = e.title
                             THEN coalesce(e.aliases, [])
                             ELSE coalesce(e.aliases, []) + $title END
        RETURN e.nodeId AS nodeId
        """,
        nodeId=node_id,
        embedding=blended_embedding,
        updatedAt=updated_at,
        title=title,
    ).single()
    return result["nodeId"]


# 매칭되는 기존 Event가 없을 때 새로 생성
def _create_new_event_node(
    session: Neo4jRunner, title: str, embedding: list[float], embedding_model: str, created_at: datetime
) -> str:
    result = session.run(
        """
        CREATE (e:Event {
            nodeId: randomUUID(), title: $title, embedding: $embedding, embeddingModel: $embeddingModel,
            createdAt: $createdAt, updatedAt: $createdAt
        })
        RETURN e.nodeId AS nodeId
        """,
        title=title,
        embedding=embedding,
        embeddingModel=embedding_model,
        createdAt=created_at,
    ).single()
    return result["nodeId"]


# AI에서 추출된 Event 후보 하나를 기존 Event와 dedup 판단해서 재사용하거나 새로 생성
# candidate_*는 이번 기사 쪽 Event가 가진 Actor/Target (아직 Neo4j에 없는, AI 응답에서 바로 파싱한 값)
def merge_event_node(
    session: Neo4jRunner,
    title: str,
    embedding: list[float],
    embedding_model: str,
    created_at: datetime,
    candidate_actor_names: list[str],
    candidate_target_names: list[str],
) -> str:
    candidates = session.run(
        """
        CALL db.index.vector.queryNodes('event_embedding_index', $topK, $embedding)
        YIELD node, score
        WHERE score >= $threshold
        RETURN node.nodeId AS nodeId
        ORDER BY score DESC
        """,
        topK=EVENT_CANDIDATE_TOP_K,
        embedding=embedding,
        threshold=EVENT_SIMILARITY_THRESHOLD,
    )

    # 유사도 높은 순서대로 하나씩 확인해서, 하드 충돌 없는 첫 후보를 매칭으로 확정
    for row in candidates:
        signals = _fetch_event_dedup_signals(session, row["nodeId"])
        if _has_event_conflict(
            signals["actorNames"], signals["targetNames"],
            candidate_actor_names, candidate_target_names,
        ):
            continue

        # 매칭 확정 - 기존 Event를 재사용하고 대표 벡터(centroid)만 갱신
        blended_embedding = _ema_update_embedding(signals["embedding"], embedding, EVENT_EMBEDDING_EMA_WEIGHT)
        return _update_matched_event(session, row["nodeId"], title, blended_embedding, created_at)

    # 후보가 하나도 없거나 전부 충돌 -> 매칭되는 기존 Event가 없는 것이므로 새로 생성
    return _create_new_event_node(session, title, embedding, embedding_model, created_at)


# 5. Statement
# Statement 노드를 생성한다
def merge_statement_node(
    session: Neo4jRunner,
    article_node_id: str,
    text: str,
    statement_type: str,
    confidence: float | None,
    created_at: datetime,
) -> str:
    result = session.run(
        """
        MATCH (a:Article {nodeId: $articleId})
        // 이미 존재할 시엔 MERGE - 같은 기사 재요청 시엔 중복 생성 안 되게 (멱등)
        MERGE (a)-[r:CONTAINS_STATEMENT]->(s:Statement {text: $text})
        // 처음 생성될 때만 CREATE 
        ON CREATE SET s.nodeId = randomUUID(), s.createdAt = $createdAt
        SET s.statementType = $statementType, s.updatedAt = $createdAt,
            r.confidence = $confidence, r.createdAt = coalesce(r.createdAt, $createdAt)
        RETURN s.nodeId AS nodeId
        """,
        articleId=article_node_id,
        text=text,
        statementType=statement_type,
        confidence=confidence,
        createdAt=created_at,
    ).single()
    return result["nodeId"]


# 6. Edge
# 엣지 타입별 Cypher 쿼리 모음 - merge_simple_edge가 여기서 타입에 맞는 쿼리를 찾아 실행
_SIMPLE_EDGE_QUERIES: dict[str, str] = {
    "MENTIONS": """
        MATCH (a {nodeId: $startId}), (b {nodeId: $endId})
        MERGE (a)-[r:MENTIONS]->(b)
        SET r.confidence = $confidence, r.createdAt = coalesce(r.createdAt, $createdAt)
        """,
    "ACTOR": """
        MATCH (a {nodeId: $startId}), (b {nodeId: $endId})
        MERGE (a)-[r:ACTOR]->(b)
        SET r.confidence = $confidence, r.createdAt = coalesce(r.createdAt, $createdAt)
        """,
    "TARGET": """
        MATCH (a {nodeId: $startId}), (b {nodeId: $endId})
        MERGE (a)-[r:TARGET]->(b)
        SET r.confidence = $confidence, r.createdAt = coalesce(r.createdAt, $createdAt)
        """,
    "PLACE": """
        MATCH (a {nodeId: $startId}), (b {nodeId: $endId})
        MERGE (a)-[r:PLACE]->(b)
        SET r.confidence = $confidence, r.createdAt = coalesce(r.createdAt, $createdAt)
        """,
    "OCCURRED_ON": """
        MATCH (a {nodeId: $startId}), (b {nodeId: $endId})
        MERGE (a)-[r:OCCURRED_ON]->(b)
        SET r.confidence = $confidence, r.extractedAt = coalesce(r.extractedAt, $createdAt)
        """,
    "ASSERTED_BY": """
        MATCH (a {nodeId: $startId}), (b {nodeId: $endId})
        MERGE (a)-[r:ASSERTED_BY]->(b)
        SET r.confidence = $confidence, r.createdAt = coalesce(r.createdAt, $createdAt)
        """,
    "ABOUT": """
        MATCH (a {nodeId: $startId}), (b {nodeId: $endId})
        MERGE (a)-[r:ABOUT]->(b)
        SET r.confidence = $confidence, r.createdAt = coalesce(r.createdAt, $createdAt)
        """,
    "CAUSES": """
        MATCH (a {nodeId: $startId}), (b {nodeId: $endId})
        MERGE (a)-[r:CAUSES]->(b)
        SET r.confidence = $confidence, r.createdAt = coalesce(r.createdAt, $createdAt), r.updatedAt = $createdAt
        """,
}


# AI 응답의 edges[] 하나를 그대로 반영 (지원 안 하는 타입은 무시)
def merge_simple_edge(
    session: Neo4jRunner, edge_type: str, start_node_id: str, end_node_id: str, confidence: float | None, created_at: datetime
) -> None:
    query = _SIMPLE_EDGE_QUERIES.get(edge_type)
    if not query:
        return
    session.run(query, startId=start_node_id, endId=end_node_id, confidence=confidence, createdAt=created_at)


# Article -> Event COVERS
def merge_covers_edge(
    session: Neo4jRunner,
    article_node_id: str,
    event_node_id: str,
    confidence: float | None,
    is_primary: bool | None,
    created_at: datetime,
) -> None:
    session.run(
        """
        MATCH (a:Article {nodeId: $articleId}), (e:Event {nodeId: $eventId})
        MERGE (a)-[r:COVERS]->(e)
        SET r.confidence = $confidence, r.createdAt = coalesce(r.createdAt, $createdAt)
        FOREACH (_ IN CASE WHEN $isPrimary IS NOT NULL THEN [1] ELSE [] END | SET r.isPrimary = $isPrimary)
        """,
        articleId=article_node_id,
        eventId=event_node_id,
        confidence=confidence,
        isPrimary=is_primary,
        createdAt=created_at,
    )


# Article -> Topic CLASSIFIED_AS
# 현재는 AI의 classification.topic 기준이라 source는 항상 AI_CLASSIFICATION
def classify_article(session: Neo4jRunner, article_node_id: str, topic_code: str, classified_at: datetime) -> None:
    session.run(
        """
        MATCH (a:Article {nodeId: $articleId}), (t:Topic {topicCode: $topicCode})
        MERGE (a)-[r:CLASSIFIED_AS]->(t)
        SET r.source = 'AI_CLASSIFICATION', r.classifiedAt = $classifiedAt
        """,
        articleId=article_node_id,
        topicCode=topic_code,
        classifiedAt=classified_at,
    )


# Event/Story/Statement -> Topic CLASSIFIED_AS
# Article의 대분류를 그대로 상속(source=ARTICLE_INHERITANCE)
def inherit_classification_from_article(session: Neo4jRunner, node_id: str, topic_code: str, classified_at: datetime) -> None:
    session.run(
        """
        MATCH (n {nodeId: $nodeId}), (t:Topic {topicCode: $topicCode})
        MERGE (n)-[r:CLASSIFIED_AS]->(t)
        SET r.source = 'ARTICLE_INHERITANCE', r.classifiedAt = $classifiedAt
        """,
        nodeId=node_id,
        topicCode=topic_code,
        classifiedAt=classified_at,
    )


# Article -> NewsOrganization PUBLISHED_BY
# spring 요청의 sourceId/sourceName을 반영
def merge_published_by_edge(session: Neo4jRunner, article_node_id: str, news_org_node_id: str, created_at: datetime) -> None:
    session.run(
        """
        MATCH (a:Article {nodeId: $articleId}), (o:Entity:NewsOrganization {nodeId: $orgId})
        MERGE (a)-[r:PUBLISHED_BY]->(o)
        SET r.createdAt = coalesce(r.createdAt, $createdAt)
        """,
        articleId=article_node_id,
        orgId=news_org_node_id,
        createdAt=created_at,
    )
