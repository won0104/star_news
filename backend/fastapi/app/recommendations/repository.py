# 추천 도메인의 Neo4j 쿼리.
from datetime import datetime

from neo4j import Session

# 유사 유저 탐색 시 fan-out을 제한하는 상위 인원 수
SIMILAR_USER_LIMIT = 50

# 후보 Event로 인정하는 최근성 기간 (일). 이보다 오래된 Event는 후보에서 제외.
RECENCY_WINDOW_DAYS = 15


# 추천 후보 공통 필터링
# - 미열람 필터: 본인이 이미 CONSUMED한 Event 제외
# - 비선호 Topic 제외 필터: 본인이 DISLIKES한 Topic으로 분류된 Event 제외
# - 최근성 필터: recency_threshold보다 오래된 Event 제외
def find_candidate_events(session: Session, user_id: int, recency_threshold: datetime) -> list[str]:
    result = session.run(
        """
        // 최근성 필터 먼저 적용 (event_occurred_at 인덱스로 좁힘)
        MATCH (candidate:Event)
        
        WHERE candidate.occurredAt >= $recencyThreshold
        // 비선호 Topic, 미열람 필터 적용 
        MATCH (u:User {userId: $userId})
        WHERE NOT (u)-[:CONSUMED]->(candidate)
          AND NOT (candidate)-[:CLASSIFIED_AS]->(:Topic)<-[:DISLIKES]-(u)

        RETURN candidate.nodeId AS eventId
        """,
        userId=user_id,
        recencyThreshold=recency_threshold,
    )
    return [record["eventId"] for record in result]


# 협업 필터링(CF) 후보 Event 조회 - 유사도는 Jaccard(교집합/합집합)로 계산
# (반환값: [{eventId, cfScore}, ...] (cfScore 내림차순))
def find_cf_candidate_events(session: Session, user_id: int) -> list[dict]:
    result = session.run(
        """
        // 본인의 전체 소비 수는 유사 유저와 무관하니 한 번만 계산 (유사 유저 수만큼 반복 계산되는 것 방지)
        MATCH (u:User {userId: $userId})-[:CONSUMED]->(ue:Event)
        WITH u, count(DISTINCT ue) AS uCount

        // 공통 CONSUMED Event 수(overlap) 계산
        MATCH (u)-[:CONSUMED]->(e:Event)<-[:CONSUMED]-(similar:User)
        WHERE similar <> u
        WITH u, uCount, similar, count(DISTINCT e) AS overlap

        // 유사 유저의 전체 소비 수 (합집합 계산용)
        MATCH (similar)-[:CONSUMED]->(se:Event)
        WITH u, similar, overlap, uCount, count(DISTINCT se) AS simCount

        // Jaccard = 교집합 / 합집합, 상위 유사 유저(SIMILAR_USER_LIMIT명)만 남김
        WITH u, similar, toFloat(overlap) / (uCount + simCount - overlap) AS jaccard
        ORDER BY jaccard DESC
        LIMIT $similarUserLimit

        // 유사 유저는 소비했지만 본인은 아직 소비하지 않은 Event, 유사도 합산으로 점수 매김
        MATCH (similar)-[:CONSUMED]->(rec:Event)
        WHERE NOT (u)-[:CONSUMED]->(rec)
        RETURN rec.nodeId AS eventId, sum(jaccard) AS cfScore
        ORDER BY cfScore DESC
        """,
        userId=user_id,
        similarUserLimit=SIMILAR_USER_LIMIT,
    )
    return [{"eventId": record["eventId"], "cfScore": record["cfScore"]} for record in result]
