# 기사 분석 도메인의 Neo4j 쿼리 (Node/Edge 생성·조회).
from datetime import datetime

from neo4j import Session

from app.articles.support.entity_filter import is_noise_entity_name, normalize_entity_name

# 1. Article
# Article 노드를 생성하거나 이미 있으면 갱신한다
def merge_article_node(
    session: Session,
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
def _merge_year_node(session: Session, year: str, created_at: datetime) -> str:
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
def _merge_month_node(session: Session, month_key: str, year: str, created_at: datetime) -> str:
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
def _merge_day_node(session: Session, day_key: str, month_key: str, created_at: datetime) -> str:
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
def merge_time_node(session: Session, time_key: str, granularity: str, created_at: datetime) -> str:
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
    session: Session, mysql_organization_id: int, name: str, created_at: datetime
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
    session: Session, canonical_name: str, entity_type: str, created_at: datetime
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
