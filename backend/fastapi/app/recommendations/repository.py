# 추천 도메인의 Neo4j 쿼리.
from neo4j import Session

# 유사 유저 탐색 시 fan-out을 제한하는 상위 인원 수
SIMILAR_USER_LIMIT = 50


# 협업 필터링(CF) 후보 Event 조회 - 유사도는 Jaccard(교집합/합집합)로 계산
# (반환값: [{eventId, cfScore}, ...] (cfScore 내림차순))
def find_cf_candidate_events(session: Session, user_id: int) -> list[dict]:
    result = session.run(
        """
        // 공통 CONSUMED Event 수(overlap) 계산
        MATCH (u:User {userId: $userId})-[:CONSUMED]->(e:Event)<-[:CONSUMED]-(similar:User)
        WHERE similar <> u
        WITH u, similar, count(DISTINCT e) AS overlap

        // 각자의 전체 소비 수 (합집합 계산용)
        MATCH (u)-[:CONSUMED]->(ue:Event)
        WITH u, similar, overlap, count(DISTINCT ue) AS uCount
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
