# /user-graph/sync가 사용하는 Neo4j User Graph 반영 쿼리 모음
from datetime import datetime

from neo4j import Session


# User 노드는 userId만 저장. 없으면 생성, 있으면 updatedAt만 갱신
def upsert_user(session: Session, user_id: int, aggregated_at: datetime) -> None:
    session.run(
        """
        MERGE (u:User {userId: $userId})
        SET u.updatedAt = $aggregatedAt
        """,
        userId=user_id,
        aggregatedAt=aggregated_at,
    )


# 이 요청이 기존 User보다 오래된 스냅샷인지 확인하기 위해 현재 updatedAt을 조회 (없으면 신규 유저라 None)
def get_user_updated_at(session: Session, user_id: int) -> datetime | None:
    record = session.run(
        "MATCH (u:User {userId: $userId}) RETURN u.updatedAt AS updatedAt",
        userId=user_id,
    ).single()
    return record["updatedAt"] if record else None


# Entity/Topic/Story를 대상으로 INTERESTED_IN 매칭. (반환값: 실제로 매칭된 노드 수)
def sync_interest_nodes(session: Session, user_id: int, node_keys: list[str], aggregated_at: datetime) -> int:
    result = session.run(
        """
        MATCH (u:User {userId: $userId})

        // 목록에 없는 기존 관심 관계 삭제
        OPTIONAL MATCH (u)-[old:INTERESTED_IN]->(n)
        WHERE NOT n.nodeId IN $nodeKeys
        DELETE old

        WITH u
        UNWIND $nodeKeys AS nodeKey

        // 목록에 있는 노드는 관계 생성/갱신
        MATCH (target {nodeId: nodeKey})
        MERGE (u)-[r:INTERESTED_IN]->(target)
        SET r.updatedAt = $aggregatedAt
        RETURN count(target) AS matchedCount
        """,
        userId=user_id,
        nodeKeys=node_keys,
        aggregatedAt=aggregated_at,
    ).single()
    return result["matchedCount"] if result else 0


# dislikeTopicCodes에 없는 기존 DISLIKES는 제거하고, 남은 목록으로 다시 MERGE. (반환값: 실제로 매칭된 Topic 수)
def sync_dislike_topics(session: Session, user_id: int, topic_codes: list[str], aggregated_at: datetime) -> int:
    result = session.run(
        """
        MATCH (u:User {userId: $userId})

        // 목록에 없는 기존 비선호 관계 삭제
        OPTIONAL MATCH (u)-[old:DISLIKES]->(t:Topic)
        WHERE NOT t.topicCode IN $topicCodes
        DELETE old

        WITH u
        UNWIND $topicCodes AS topicCode

        // 목록에 있는 Topic은 관계 생성/갱신
        MATCH (t:Topic {topicCode: topicCode})
        MERGE (u)-[r:DISLIKES]->(t)
        SET r.updatedAt = $aggregatedAt
        RETURN count(t) AS matchedCount
        """,
        userId=user_id,
        topicCodes=topic_codes,
        aggregatedAt=aggregated_at,
    ).single()
    return result["matchedCount"] if result else 0


# 소비 이벤트 반영. 반환값: 실제로 매칭된 Event 수
def sync_consumed_events(
    session: Session, user_id: int, consumed_events: list[dict], aggregated_at: datetime
) -> int:
    result = session.run(
        """
        MATCH (u:User {userId: $userId})
        UNWIND $events AS event
        MATCH (e:Event {nodeId: event.eventId})
        MERGE (u)-[r:CONSUMED]->(e)
        SET r.count = event.count,
            r.lastViewedAt = event.lastViewedAt,
            r.eventFavorited = event.eventFavorited,
            r.updatedAt = $aggregatedAt
        RETURN count(e) AS matchedCount
        """,
        userId=user_id,
        events=consumed_events,
        aggregatedAt=aggregated_at,
    ).single()
    return result["matchedCount"] if result else 0


# Story Coverage 계산
# CONSUMED 반영 직후 호출. Story별 소비 Event 수를 다시 세어 COVERED에 캐싱한다.
def refresh_story_coverage(session: Session, user_id: int, aggregated_at: datetime) -> None:
    session.run(
        """
        // 유저가 소비한 Event들이 속한 Story별로, 소비한 Event 수 집계
        MATCH (u:User {userId: $userId})-[:CONSUMED]->(e:Event)-[:PART_OF]->(s:Story)
        WITH u, s, count(DISTINCT e) AS consumedCount

        // 같은 Story의 전체 Event 수 집계
        MATCH (s)<-[:PART_OF]-(allE:Event)
        WITH u, s, consumedCount, count(allE) AS totalCount

        // Coverage 계산해서 COVERED 관계에 저장
        MERGE (u)-[c:COVERED]->(s)
        SET c.consumedEventCount = consumedCount,
            c.totalEventCount = totalCount,
            c.coverageRate = toFloat(consumedCount) / totalCount,
            c.updatedAt = $aggregatedAt
        """,
        userId=user_id,
        aggregatedAt=aggregated_at,
    )
