# 기사 분석 도메인의 Neo4j 쿼리 (Node/Edge 생성·조회).
import math
from datetime import datetime, timedelta
from uuid import UUID

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
# EVENT_SIMILARITY_THRESHOLD를 raw cosine 기준으로 환산한 값
# - Neo4j 벡터 인덱스 score는 (1+raw_cosine)/2 로 변환된 값이라, 같은 기준으로 파이썬에서 직접 비교하려면 역산이 필요함
EVENT_RAW_COSINE_THRESHOLD = 2 * EVENT_SIMILARITY_THRESHOLD - 1

# Story dedup 벡터 유사도 임계값 - Event(0.92)보다는 낮게 유지
STORY_SIMILARITY_THRESHOLD = 0.8
# 벡터 검색 시 후보로 가져올 최대 개수
STORY_CANDIDATE_TOP_K = 8
# 대표 벡터(centroid) 갱신 시 새 임베딩을 반영하는 비율 (지수이동평균) - Event와 동일 가중치 재사용
STORY_EMBEDDING_EMA_WEIGHT = 0.15
# 이보다 오래 새 Event가 안 붙은 Story/외톨이 Event는 후보에서 제외 (죽은 흐름으로 간주)
STORY_STALE_DAYS = 30
# Story 편입 시 Actor/Target 충돌을 체크할 때, 최근 이만큼의 Event만 본다
STORY_RECENT_MEMBER_WINDOW = 3


class ArticleIdentityConflictError(RuntimeError):
    """실제 MySQL 기사 ID가 레거시 비UUID Article에 잘못 연결된 경우."""


def _is_uuid(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        UUID(value)
    except (ValueError, AttributeError):
        return False
    return True


# 1. Article
# 이미 완전히 분석 완료된 기사인지 확인
# Spring 타임아웃 후 재시도가 들어와도 AI를 또 부르지 않기 위한 단축 경로
def find_completed_analysis(session: Neo4jRunner, mysql_article_id: int) -> dict | None:
    result = session.run(
        """
        MATCH (a:Article {mysqlArticleId: $mysqlArticleId})-[:CLASSIFIED_AS]->(t:Topic)
        WHERE a.subtopicCode IS NOT NULL AND EXISTS { (a)-[:COVERS]->(:Event) }
        RETURN a.nodeId AS nodeId, a.subtopicCode AS subtopicCode, t.topicCode AS topicCode
        LIMIT 1
        """,
        mysqlArticleId=mysql_article_id,
    ).single()
    if result is None:
        return None
    return {"nodeId": result["nodeId"], "subtopicCode": result["subtopicCode"], "topicCode": result["topicCode"]}


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
    node_id = result["nodeId"]
    if not _is_uuid(node_id):
        # 이 예외는 execute_write 콜백 밖으로 전파되어 위 SET까지 포함한 전체
        # 기사 분석 트랜잭션을 롤백한다. ART-* 번들 노드에 운영 기사를
        # 덮어쓰는 과거 사고를 조용히 반복하지 않기 위한 fail-fast 방어다.
        raise ArticleIdentityConflictError(
            f"mysqlArticleId={mysql_article_id} is already bound to non-UUID nodeId={node_id!r}"
        )
    return node_id


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


# Entity 보조 라벨 설정 - entityType 값에 따라 세부 라벨(Person/Location/...)을 추가로 붙임
_ENTITY_SECONDARY_LABEL_CYPHER = """
        FOREACH (_ IN CASE WHEN e.entityType = 'PERSON' THEN [1] ELSE [] END | SET e:Person)
        FOREACH (_ IN CASE WHEN e.entityType = 'LOCATION' THEN [1] ELSE [] END | SET e:Location)
        FOREACH (_ IN CASE WHEN e.entityType = 'ORGANIZATION' THEN [1] ELSE [] END | SET e:Organization)
        FOREACH (_ IN CASE WHEN e.entityType = 'PRODUCT' THEN [1] ELSE [] END | SET e:Product)
        FOREACH (_ IN CASE WHEN e.entityType = 'GENERIC' THEN [1] ELSE [] END | SET e:Generic)
"""


# 기사 본문에서 뽑은 Entity를 생성하거나 이미 있으면 재사용
def merge_extracted_entity(
    session: Neo4jRunner, canonical_name: str, entity_type: str, created_at: datetime,
    aliases: list[str] | None = None,
) -> str | None:

    # 노이즈면 None
    normalized_name = normalize_entity_name(canonical_name)
    if is_noise_entity_name(normalized_name):
        return None

    # 매칭 후보 순서: 자기 canonicalName 먼저, 그다음 aliases(정규화해서 비교)
    candidate_names = [
        n for n in dict.fromkeys([normalized_name] + [normalize_entity_name(a) for a in (aliases or [])]) if n
    ]

    # 후보 이름 중 하나라도 canonicalName이 겹치는 기존 Entity를 찾는다
    existing = session.run(
        """
        UNWIND range(0, size($candidateNames) - 1) AS idx
        WITH $candidateNames[idx] AS name, idx
        MATCH (e:Entity {canonicalName: name})
        WHERE e.entityType = $entityType OR e.entityType IS NULL
        RETURN e.nodeId AS nodeId, name AS matchedName, idx
        ORDER BY idx
        LIMIT 1
        """,
        candidateNames=candidate_names,
        entityType=entity_type,
    ).single()

    # 매칭되는 기존 Entity를 찾음 - 새로 안 만들고 이 노드를 그대로 재사용
    if existing:
        node_id = existing["nodeId"]
        new_alias = canonical_name if existing["matchedName"] != normalized_name else None

        session.run(
            """
            MATCH (e:Entity {nodeId: $nodeId})
            SET e.entityType = coalesce(e.entityType, $entityType), e.updatedAt = $createdAt,
                // newAlias가 없거나 이미 있는 표현이면 그대로, 새 표현이면 이어붙임
                e.aliases = CASE
                    WHEN $newAlias IS NULL OR $newAlias IN coalesce(e.aliases, []) THEN coalesce(e.aliases, [])
                    ELSE coalesce(e.aliases, []) + $newAlias
                END
            """
            + _ENTITY_SECONDARY_LABEL_CYPHER,
            nodeId=node_id,
            entityType=entity_type,
            createdAt=created_at,
            newAlias=new_alias,
        )
        return node_id

    # 후보 중 아무것도 안 겹침 - 완전히 새로운 Entity라 새 노드 생성
    result = session.run(
        """
        CREATE (e:Entity {
            nodeId: randomUUID(), canonicalName: $canonicalName, entityType: $entityType,
            createdAt: $createdAt, updatedAt: $createdAt, aliases: []
        })
        """
        + _ENTITY_SECONDARY_LABEL_CYPHER
        + "        RETURN e.nodeId AS nodeId",
        canonicalName=normalized_name,
        entityType=entity_type,
        createdAt=created_at,
    ).single()
    return result["nodeId"]

# 4. Event
# 벡터 유사도가 높아도, 등장인물/대상이 겹치는 게 하나도 없으면 "확실히 다른 사건"으로 확정 판단.
# - 둘 다 Actor가 2명 이상인데 겹치는 사람이 없음
# - 둘 다 Target이 있는데 겹치는 대상이 없음
def _are_definitely_different_events(
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
def _update_matched_event(
    session: Neo4jRunner, node_id: str, title: str, blended_embedding: list[float], occurred_at: datetime, updated_at: datetime
) -> str:
    result = session.run(
        """
        MATCH (e:Event {nodeId: $nodeId})
        SET e.embedding = $embedding, e.updatedAt = $updatedAt, e.occurredAt = $occurredAt,
            e.aliases = CASE WHEN $title IN coalesce(e.aliases, []) OR $title = e.title
                             THEN coalesce(e.aliases, [])
                             ELSE coalesce(e.aliases, []) + $title END
        RETURN e.nodeId AS nodeId
        """,
        nodeId=node_id,
        embedding=blended_embedding,
        updatedAt=updated_at,
        occurredAt=occurred_at,
        title=title,
    ).single()
    return result["nodeId"]


# 매칭되는 기존 Event가 없을 때 새로 생성
# occurredAt은 기사 발행 시각을 그대로 씀 - AI가 문장 단위 실제 발생 시각을 안 주기 때문
def _create_new_event_node(
    session: Neo4jRunner, title: str, embedding: list[float], embedding_model: str, occurred_at: datetime, created_at: datetime
) -> str:
    result = session.run(
        """
        CREATE (e:Event {
            nodeId: randomUUID(), title: $title, embedding: $embedding, embeddingModel: $embeddingModel,
            occurredAt: $occurredAt, createdAt: $createdAt, updatedAt: $createdAt
        })
        RETURN e.nodeId AS nodeId
        """,
        title=title,
        embedding=embedding,
        embeddingModel=embedding_model,
        occurredAt=occurred_at,
        createdAt=created_at,
    ).single()
    return result["nodeId"]


# 두 임베딩의 코사인 유사도(raw, Neo4j 벡터 인덱스 score로 변환하기 전 값)
# 같은 트랜잭션 안에서 아직 커밋 안 된 노드끼리 비교할 때 씀
def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


# raw cosine 유사도를 Neo4j 벡터 인덱스 score 형태로 변환
# - 커밋된 후보(Neo4j가 준 score)와 in-batch 후보(파이썬에서 직접 계산한 raw cosine)를 같은 척도로 섞어서 비교하기 위함
def _cosine_to_score(raw_cosine: float) -> float:
    return (1 + raw_cosine) / 2


# AI에서 추출된 Event 후보 하나를 기존 Event와 dedup 판단해서 재사용하거나 새로 생성
# candidate_*는 이번 기사 쪽 Event가 가진 Actor/Target (아직 Neo4j에 없는, AI 응답에서 바로 파싱한 값)
# in_batch_candidates: 같은 기사(같은 트랜잭션) 안에서 이미 처리한 Event들
def merge_event_node(
    session: Neo4jRunner,
    title: str,
    embedding: list[float],
    embedding_model: str,
    occurred_at: datetime,
    created_at: datetime,
    candidate_actor_names: list[str],
    candidate_target_names: list[str],
    in_batch_candidates: list[dict] | None = None,
) -> tuple[str, bool]:
    # 1) 같은 기사 안에서 먼저 처리한 Event부터 확인 (파이썬 직접 비교, 유사도 높은 순)
    similar_in_batch = sorted(
        ((c, _cosine_similarity(c["embedding"], embedding)) for c in (in_batch_candidates or [])),
        key=lambda pair: pair[1],
        reverse=True,
    )
    for candidate, similarity in similar_in_batch:
        if similarity < EVENT_RAW_COSINE_THRESHOLD:
            break  # 유사도 순 정렬이라 이후로는 전부 더 낮음
        if _are_definitely_different_events(
            candidate["actorNames"], candidate["targetNames"],
            candidate_actor_names, candidate_target_names,
        ):
            continue

        # 매칭 확정 - 기존 Event를 재사용하고 대표 벡터(centroid)만 갱신
        blended_embedding = _ema_update_embedding(candidate["embedding"], embedding, EVENT_EMBEDDING_EMA_WEIGHT)
        return _update_matched_event(session, candidate["nodeId"], title, blended_embedding, occurred_at, created_at), False

    # 2) 여기서 못 찾으면 기존 방식대로 - 이미 커밋된(다른 기사에서 만들어진) Event 대상 벡터 검색
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

    # 유사도 높은 순서대로 하나씩 확인해서, "확실히 다른 사건"이 아닌 첫 후보를 매칭으로 확정
    for row in candidates:
        signals = _fetch_event_dedup_signals(session, row["nodeId"])
        if _are_definitely_different_events(
            signals["actorNames"], signals["targetNames"],
            candidate_actor_names, candidate_target_names,
        ):
            continue

        # 매칭 확정 - 기존 Event를 재사용하고 대표 벡터(centroid)만 갱신
        blended_embedding = _ema_update_embedding(signals["embedding"], embedding, EVENT_EMBEDDING_EMA_WEIGHT)
        return _update_matched_event(session, row["nodeId"], title, blended_embedding, occurred_at, created_at), False

    # 후보가 하나도 없거나 전부 충돌 -> 매칭되는 기존 Event가 없는 것이므로 새로 생성
    return _create_new_event_node(session, title, embedding, embedding_model, occurred_at, created_at), True


# 5. Story
# Event가 확정될 때마다 이 함수로 어느 Story에 속할지 직접 판단
# 기존 Story 후보들 검색(유사도 높은 순) - Topic이 같고, 너무 오래 방치되지 않은(죽지 않은) Story만
def _find_story_candidates(
    session: Neo4jRunner, embedding: list[float], topic_code: str, stale_cutoff: datetime
) -> list[dict]:
    result = session.run(
        """
        CALL db.index.vector.queryNodes('story_embedding_index', $topK, $embedding)
        YIELD node, score
        WHERE score >= $threshold
        MATCH (node)-[:CLASSIFIED_AS]->(:Topic {topicCode: $topicCode})
        WHERE node.lastEventAddedAt >= $staleCutoff
        RETURN node.nodeId AS nodeId, node.embedding AS embedding, score
        ORDER BY score DESC
        """,
        topK=STORY_CANDIDATE_TOP_K,
        embedding=embedding,
        threshold=STORY_SIMILARITY_THRESHOLD,
        topicCode=topic_code,
        staleCutoff=stale_cutoff,
    )
    return result.data()


# Story 후보 하나의 "최근 STORY_RECENT_MEMBER_WINDOW개 멤버"의 Actor/Target을 조회
def _fetch_story_recent_member_signals(session: Neo4jRunner, story_node_id: str) -> list[dict]:
    result = session.run(
        """
        MATCH (e:Event)-[r:PART_OF]->(:Story {nodeId: $storyId})
        WITH e ORDER BY r.assignedAt DESC LIMIT $window
        OPTIONAL MATCH (e)-[:ACTOR]->(actor:Entity)
        OPTIONAL MATCH (e)-[:TARGET]->(target:Entity)
        WITH e, collect(DISTINCT actor.canonicalName) AS actorNames, collect(DISTINCT target.canonicalName) AS targetNames
        RETURN actorNames, targetNames
        """,
        storyId=story_node_id,
        window=STORY_RECENT_MEMBER_WINDOW,
    )
    return [{"actorNames": list(r["actorNames"]), "targetNames": list(r["targetNames"])} for r in result]


# Story가 새 Event와 "확실히 무관"한지 판단 - 최근 멤버 전원이 각각 다 "확실히 다른 사건"으로 나와야 무관 확정
def _is_definitely_unrelated_to_story(
    recent_member_signals: list[dict], new_actor_names: list[str], new_target_names: list[str]
) -> bool:
    # 멤버가 하나도 없으면(막 만들어진 Story) 비교할 게 없으니 무관하다고 단정하지 않음(=이 Story 후보 유지)
    if not recent_member_signals:
        return False
    return all(
        _are_definitely_different_events(member["actorNames"], member["targetNames"], new_actor_names, new_target_names)
        for member in recent_member_signals
    )


# 아직 어떤 Story에도 안 속한 "외톨이" Event 후보들 검색(유사도 높은 순) - Actor/Target도 같이 조회
def _find_orphan_event_candidates(
    session: Neo4jRunner, embedding: list[float], topic_code: str, stale_cutoff: datetime, exclude_event_id: str
) -> list[dict]:
    result = session.run(
        """
        CALL db.index.vector.queryNodes('event_embedding_index', $topK, $embedding)
        YIELD node, score
        WHERE score >= $threshold AND node.nodeId <> $excludeEventId AND NOT (node)-[:PART_OF]->(:Story)
        MATCH (node)-[:CLASSIFIED_AS]->(:Topic {topicCode: $topicCode})
        WHERE node.updatedAt >= $staleCutoff
        OPTIONAL MATCH (node)-[:ACTOR]->(actor:Entity)
        OPTIONAL MATCH (node)-[:TARGET]->(target:Entity)
        WITH node, score, collect(DISTINCT actor.canonicalName) AS actorNames, collect(DISTINCT target.canonicalName) AS targetNames
        RETURN node.nodeId AS nodeId, node.title AS title, node.embedding AS embedding, score, actorNames, targetNames
        ORDER BY score DESC
        """,
        topK=STORY_CANDIDATE_TOP_K,
        embedding=embedding,
        threshold=STORY_SIMILARITY_THRESHOLD,
        topicCode=topic_code,
        staleCutoff=stale_cutoff,
        excludeEventId=exclude_event_id,
    )
    return [
        {
            "nodeId": r["nodeId"],
            "title": r["title"],
            "embedding": r["embedding"],
            "score": r["score"],
            "actorNames": list(r["actorNames"]),
            "targetNames": list(r["targetNames"]),
        }
        for r in result
    ]


# 새 Story 생성
def _create_new_story_node(
    session: Neo4jRunner,
    title: str,
    embedding: list[float],
    embedding_model: str,
    topic_code: str,
    occurred_at: datetime,
    added_at: datetime,
) -> str:
    result = session.run(
        """
        MATCH (t:Topic {topicCode: $topicCode})
        CREATE (s:Story {
            nodeId: randomUUID(), title: $title, embedding: $embedding, embeddingModel: $embeddingModel,
            startedAt: $occurredAt, lastEventAt: $occurredAt, lastEventAddedAt: $addedAt
        })
        MERGE (s)-[r:CLASSIFIED_AS]->(t)
        SET r.source = 'ARTICLE_INHERITANCE', r.classifiedAt = $addedAt
        RETURN s.nodeId AS nodeId
        """,
        title=title,
        embedding=embedding,
        embeddingModel=embedding_model,
        topicCode=topic_code,
        occurredAt=occurred_at,
        addedAt=added_at,
    ).single()
    return result["nodeId"]


# 기존 Story에 새 Event가 편입될 때 대표 벡터(centroid)와 최신 시각들을 갱신
def _update_matched_story(
    session: Neo4jRunner, node_id: str, blended_embedding: list[float], occurred_at: datetime, added_at: datetime
) -> str:
    result = session.run(
        """
        MATCH (s:Story {nodeId: $nodeId})
        SET s.embedding = $embedding,
            s.lastEventAt = CASE WHEN $occurredAt > s.lastEventAt THEN $occurredAt ELSE s.lastEventAt END,
            s.lastEventAddedAt = $addedAt
        RETURN s.nodeId AS nodeId
        """,
        nodeId=node_id,
        embedding=blended_embedding,
        occurredAt=occurred_at,
        addedAt=added_at,
    ).single()
    return result["nodeId"]


# Event -> Story PART_OF edge 연결
def merge_part_of_edge(session: Neo4jRunner, event_node_id: str, story_node_id: str, relevance: float, assigned_at: datetime) -> None:
    session.run(
        """
        MATCH (e:Event {nodeId: $eventId}), (s:Story {nodeId: $storyId})
        MERGE (e)-[r:PART_OF]->(s)
        SET r.relevance = $relevance, r.assignedAt = coalesce(r.assignedAt, $assignedAt)
        """,
        eventId=event_node_id,
        storyId=story_node_id,
        relevance=relevance,
        assignedAt=assigned_at,
    )


# Event 하나를 Story에 배정한다
def assign_event_to_story(
    session: Neo4jRunner,
    event_node_id: str,
    event_title: str,
    event_embedding: list[float],
    embedding_model: str,
    topic_code: str,
    occurred_at: datetime,
    now: datetime,
    actor_names: list[str],
    target_names: list[str],
    in_batch_stories: list[dict] | None = None,
    in_batch_orphans: list[dict] | None = None,
) -> str | None:
    # in_batch_stories/in_batch_orphans: "기사 내" 후보 저장소
    # - 같은 기사(같은 트랜잭션) 안에서 방금 새로 만든 Story/외톨이 Event를 담아둠
    if in_batch_stories is None:
        in_batch_stories = []
    if in_batch_orphans is None:
        in_batch_orphans = []

    stale_cutoff = now - timedelta(days=STORY_STALE_DAYS)

    # 1) Story 후보
    # - 기사 외(다른 기사에서 이미 만들어져 커밋된 Story) - 벡터 인덱스 검색으로 찾음
    story_candidates = list(_find_story_candidates(session, event_embedding, topic_code, stale_cutoff))
    # - 기사 내(이 기사 안에서 방금 만든 Story, 아직 미커밋) - 벡터 인덱스에 안 잡히니 파이썬으로 직접 비교
    for story in in_batch_stories:
        if story["topicCode"] != topic_code:
            continue
        score = _cosine_to_score(_cosine_similarity(story["embedding"], event_embedding))
        if score >= STORY_SIMILARITY_THRESHOLD:
            story_candidates.append({"nodeId": story["nodeId"], "embedding": story["embedding"], "score": score})
    story_candidates.sort(key=lambda c: c["score"], reverse=True)  # 기사 외 + 기사 내를 합쳐서 다시 점수순 정렬

    # 유사도 높은 순으로 보면서, 확실히 무관한 게 아닌 첫 후보를 채택
    story_candidate = None
    for candidate in story_candidates:
        recent_signals = _fetch_story_recent_member_signals(session, candidate["nodeId"])
        if _is_definitely_unrelated_to_story(recent_signals, actor_names, target_names):
            continue
        story_candidate = candidate
        break

    # 2) 외톨이 Event 후보
    # - 기사 외(다른 기사에서 이미 만들어져 커밋된 외톨이 Event) - 벡터 인덱스 검색으로 찾음
    orphan_candidates = list(_find_orphan_event_candidates(session, event_embedding, topic_code, stale_cutoff, event_node_id))
    # - 기사 내(이 기사 안에서 아직 Story 없이 남은 Event, 아직 미커밋) - 마찬가지로 파이썬 직접 비교
    for orphan in in_batch_orphans:
        if orphan["topicCode"] != topic_code:
            continue
        score = _cosine_to_score(_cosine_similarity(orphan["embedding"], event_embedding))
        if score >= STORY_SIMILARITY_THRESHOLD:
            orphan_candidates.append({**orphan, "score": score})
    orphan_candidates.sort(key=lambda c: c["score"], reverse=True)  # 기사 외 + 기사 내를 합쳐서 다시 점수순 정렬

    # 마찬가지로 확실히 다른 사건이 아닌 첫 후보를 채택
    orphan_candidate = None
    for candidate in orphan_candidates:
        if _are_definitely_different_events(candidate["actorNames"], candidate["targetNames"], actor_names, target_names):
            continue
        orphan_candidate = candidate
        break

    # 3) 최종 결정 - Story 후보가 있고, 외톨이 후보보다 점수가 같거나 높으면 Story 편입을 우선함
    if story_candidate and (not orphan_candidate or story_candidate["score"] >= orphan_candidate["score"]):
        # 기존 Story 편입 - 대표 벡터만 갱신
        blended_embedding = _ema_update_embedding(story_candidate["embedding"], event_embedding, STORY_EMBEDDING_EMA_WEIGHT)
        story_node_id = _update_matched_story(session, story_candidate["nodeId"], blended_embedding, occurred_at, now)
        merge_part_of_edge(session, event_node_id, story_node_id, story_candidate["score"], now)
        return story_node_id

    if orphan_candidate:
        # 외톨이 Event 둘을 묶어 새 Story로 승격 - 먼저 있던 Event의 title을 시작점으로 사용
        blended_embedding = _ema_update_embedding(orphan_candidate["embedding"], event_embedding, STORY_EMBEDDING_EMA_WEIGHT)
        story_node_id = _create_new_story_node(
            session, orphan_candidate["title"], blended_embedding, embedding_model, topic_code, occurred_at, now
        )
        merge_part_of_edge(session, orphan_candidate["nodeId"], story_node_id, 1.0, now)
        merge_part_of_edge(session, event_node_id, story_node_id, orphan_candidate["score"], now)

        # (기사 내 갱신) 방금 승격시킨 외톨이는 더 이상 외톨이가 아니므로 목록에서 빼고, 새로 만든 Story는 이 기사 안에서 이어질 다른 Event가 찾을 수 있게 등록
        in_batch_orphans[:] = [o for o in in_batch_orphans if o["nodeId"] != orphan_candidate["nodeId"]]
        in_batch_stories.append({"nodeId": story_node_id, "embedding": blended_embedding, "topicCode": topic_code})
        return story_node_id

    # 후보가 하나도 없음 - 아직은 외톨이 Event로 남김
    in_batch_orphans.append({
        "nodeId": event_node_id, "title": event_title, "embedding": event_embedding,
        "topicCode": topic_code, "actorNames": actor_names, "targetNames": target_names,
    })
    return None


# 6. Statement
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
            r.confidence = CASE WHEN $confidence IS NULL OR $confidence <= coalesce(r.confidence, -1.0) THEN r.confidence ELSE $confidence END, r.createdAt = coalesce(r.createdAt, $createdAt)
        RETURN s.nodeId AS nodeId
        """,
        articleId=article_node_id,
        text=text,
        statementType=statement_type,
        confidence=confidence,
        createdAt=created_at,
    ).single()
    return result["nodeId"]


# 7. Edge
# 같은 관계가 여러 기사에서 다시 나오면 confidence 는 가장 높은 값을 남긴다.
# 덮어쓰면 확신 높게 여러 번 나온 관계가 마지막 기사 하나 때문에 낮아진다.
# 이 값은 Spring 주변 그래프의 순위·선 굵기와 추천 상세의 기사 순서에 쓰인다.
# 엣지 타입별 Cypher 쿼리 모음 - merge_simple_edge가 여기서 타입에 맞는 쿼리를 찾아 실행
_SIMPLE_EDGE_QUERIES: dict[str, str] = {
    "MENTIONS": """
        MATCH (a {nodeId: $startId}), (b {nodeId: $endId})
        MERGE (a)-[r:MENTIONS]->(b)
        SET r.confidence = CASE WHEN $confidence IS NULL OR $confidence <= coalesce(r.confidence, -1.0) THEN r.confidence ELSE $confidence END, r.createdAt = coalesce(r.createdAt, $createdAt)
        """,
    "ACTOR": """
        MATCH (a {nodeId: $startId}), (b {nodeId: $endId})
        MERGE (a)-[r:ACTOR]->(b)
        SET r.confidence = CASE WHEN $confidence IS NULL OR $confidence <= coalesce(r.confidence, -1.0) THEN r.confidence ELSE $confidence END, r.createdAt = coalesce(r.createdAt, $createdAt)
        """,
    "TARGET": """
        MATCH (a {nodeId: $startId}), (b {nodeId: $endId})
        MERGE (a)-[r:TARGET]->(b)
        SET r.confidence = CASE WHEN $confidence IS NULL OR $confidence <= coalesce(r.confidence, -1.0) THEN r.confidence ELSE $confidence END, r.createdAt = coalesce(r.createdAt, $createdAt)
        """,
    "PLACE": """
        MATCH (a {nodeId: $startId}), (b {nodeId: $endId})
        MERGE (a)-[r:PLACE]->(b)
        SET r.confidence = CASE WHEN $confidence IS NULL OR $confidence <= coalesce(r.confidence, -1.0) THEN r.confidence ELSE $confidence END, r.createdAt = coalesce(r.createdAt, $createdAt)
        """,
    "OCCURRED_ON": """
        MATCH (a {nodeId: $startId}), (b {nodeId: $endId})
        MERGE (a)-[r:OCCURRED_ON]->(b)
        SET r.confidence = CASE WHEN $confidence IS NULL OR $confidence <= coalesce(r.confidence, -1.0) THEN r.confidence ELSE $confidence END, r.extractedAt = coalesce(r.extractedAt, $createdAt)
        """,
    "ASSERTED_BY": """
        MATCH (a {nodeId: $startId}), (b {nodeId: $endId})
        MERGE (a)-[r:ASSERTED_BY]->(b)
        SET r.confidence = CASE WHEN $confidence IS NULL OR $confidence <= coalesce(r.confidence, -1.0) THEN r.confidence ELSE $confidence END, r.createdAt = coalesce(r.createdAt, $createdAt)
        """,
    "ABOUT": """
        MATCH (a {nodeId: $startId}), (b {nodeId: $endId})
        MERGE (a)-[r:ABOUT]->(b)
        SET r.confidence = CASE WHEN $confidence IS NULL OR $confidence <= coalesce(r.confidence, -1.0) THEN r.confidence ELSE $confidence END, r.createdAt = coalesce(r.createdAt, $createdAt)
        """,
    "CAUSES": """
        MATCH (a {nodeId: $startId}), (b {nodeId: $endId})
        MERGE (a)-[r:CAUSES]->(b)
        SET r.confidence = CASE WHEN $confidence IS NULL OR $confidence <= coalesce(r.confidence, -1.0) THEN r.confidence ELSE $confidence END, r.createdAt = coalesce(r.createdAt, $createdAt), r.updatedAt = $createdAt
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
def reset_covers_primary(
    session: Neo4jRunner,
    article_node_id: str,
) -> None:
    session.run(
        """
        MATCH (:Article {nodeId: $articleId})-[r:COVERS]->(:Event)
        SET r.isPrimary = false
        """,
        articleId=article_node_id,
    )


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
        SET r.confidence = CASE WHEN $confidence IS NULL OR $confidence <= coalesce(r.confidence, -1.0) THEN r.confidence ELSE $confidence END, r.createdAt = coalesce(r.createdAt, $createdAt)
        FOREACH (_ IN CASE WHEN $isPrimary IS NOT NULL THEN [1] ELSE [] END | SET r.isPrimary = $isPrimary)
        // 이 기사에서 처음으로 primary가 되는 순간 :PrimaryEvent 라벨을 붙인다 (CBF 전용 인덱스 대상)
        FOREACH (_ IN CASE WHEN $isPrimary = true THEN [1] ELSE [] END | SET e:PrimaryEvent)
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
