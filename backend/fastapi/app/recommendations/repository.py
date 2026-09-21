# 추천 도메인의 Neo4j 쿼리.
from datetime import datetime

from neo4j import Session

# 유사 유저 탐색 시 fan-out을 제한하는 상위 인원 수
SIMILAR_USER_LIMIT = 50

# 후보 Event로 인정하는 최근성 기간 (일) - 이보다 오래된 Event는 후보에서 제외
RECENCY_WINDOW_DAYS = 15

# 콘텐츠 기반 추천(CBF)에서 최종적으로 반환할 유사 Event 개수
CONTENT_SIMILAR_EVENT_LIMIT = 20

# Cold Start 폴백에서 최종적으로 반환할 Event 개수
FALLBACK_EVENT_LIMIT = 10

# 관심 기반 추천에서 최종적으로 반환할 Event 개수
FINAL_RECOMMENDATION_LIMIT = 10


# 1. 공통 후보 조건
# (미열람/비선호 Topic 제외/관심 Topic 하드 필터/최근성)을 매번 새로 안 만들도록 한 곳에서 조립.
_CANDIDATE_CONDITIONS = """
  AND NOT (u)-[:CONSUMED]->(candidate)
  AND NOT (candidate)-[:CLASSIFIED_AS]->(:Topic)<-[:DISLIKES]-(u)
  AND ($interestedTopicCodes IS NULL OR EXISTS {
      (candidate)-[:CLASSIFIED_AS]->(t:Topic) WHERE t.topicCode IN $interestedTopicCodes
  })
  AND ($recencyThreshold IS NULL OR candidate.occurredAt >= $recencyThreshold)
"""


# 2. 협업 필터링(CF) 후보 Event 조회 - 유사도는 Jaccard(교집합/합집합)로 계산
# (반환값: [{eventId, cfScore}, ...] (cfScore 내림차순))
def find_cf_candidate_events(
    session: Session,
    user_id: int,
    interested_topic_codes: list[str] | None = None,
    recency_threshold: datetime | None = None,
) -> list[dict]:
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

        // 유사 유저는 소비했지만 본인은 아직 소비하지 않은 Event, 공통 후보 조건까지 적용해 유사도 합산으로 점수 매김
        MATCH (similar)-[:CONSUMED]->(candidate:Event)
        WHERE true
        """
        + _CANDIDATE_CONDITIONS
        + """
        RETURN candidate.nodeId AS eventId, sum(jaccard) AS cfScore
        ORDER BY cfScore DESC
        """,
        userId=user_id,
        similarUserLimit=SIMILAR_USER_LIMIT,
        interestedTopicCodes=interested_topic_codes or None,
        recencyThreshold=recency_threshold,
    )
    return [{"eventId": record["eventId"], "cfScore": record["cfScore"]} for record in result]


# 3. 콘텐츠 기반 필터링(CBF)
# 유저 프로필 벡터 계산에 쓸 CONSUMED Event 임베딩 조회 (eventClickCount/lastViewedAt은 가중치 계산용)
def find_consumed_events_with_embeddings(session: Session, user_id: int) -> list[dict]:
    result = session.run(
        """
        // 유저가 소비한 Event 중 임베딩 있는 것만
        MATCH (u:User {userId: $userId})-[r:CONSUMED]->(e:Event)
        WHERE e.embedding IS NOT NULL
        RETURN e.embedding AS embedding, r.eventClickCount AS eventClickCount, r.lastViewedAt AS lastViewedAt,
               coalesce(r.eventFavorited, false) AS isFavorited
        """,
        userId=user_id,
    )
    return [
        {
            "embedding": record["embedding"],
            "eventClickCount": record["eventClickCount"],
            # neo4j.time.DateTime -> 파이썬 기본 datetime 변환 (그대로 두면 service.py에서 뺄셈 시 에러남)
            "lastViewedAt": record["lastViewedAt"].to_native(),
            "isFavorited": record["isFavorited"],
        }
        for record in result
    ]


# 프로필 벡터로 벡터 인덱스에서 유사 Event 검색, 공통 후보 조건까지 적용
def find_similar_events_by_vector(
    session: Session,
    profile_vector: list[float],
    user_id: int,
    interested_topic_codes: list[str] | None,
    recency_threshold: datetime,
    raw_limit: int,
    limit: int = CONTENT_SIMILAR_EVENT_LIMIT,
) -> list[dict]:
    result = session.run(
        """
        MATCH (u:User {userId: $userId})

        // 벡터 인덱스에서 프로필 벡터와 가까운 순으로 rawLimit개 조회
        CALL db.index.vector.queryNodes('event_embedding_index', $rawLimit, $profileVector)
        YIELD node AS candidate, score

        // 공통 후보 조건(미열람/비선호 Topic/관심 Topic/최근성) 적용
        WHERE true
        """
        + _CANDIDATE_CONDITIONS
        + """
        RETURN candidate.nodeId AS eventId, score AS contentScore
        ORDER BY contentScore DESC
        LIMIT $limit
        """,
        userId=user_id,
        profileVector=profile_vector,
        rawLimit=raw_limit,
        limit=limit, # raw_limit은 호출측이 조절 - 필터 통과분이 부족하면 호출측이 더 큰 raw_limit으로 재시도한다
        interestedTopicCodes=interested_topic_codes or None,
        recencyThreshold=recency_threshold,
    )
    return [{"eventId": record["eventId"], "contentScore": record["contentScore"]} for record in result]


# 4. Cold Start (CONSUMED 이력 없는 유저) 폴백
# 판별 - 유저에게 CONSUMED 이력이 하나라도 있는지 확인
def has_consumption_history(session: Session, user_id: int) -> bool:
    result = session.run(
        "MATCH (u:User {userId: $userId}) RETURN EXISTS { (u)-[:CONSUMED]->() } AS hasHistory",
        userId=user_id,
    ).single()
    return bool(result["hasHistory"]) if result else False


# 유저가 관심 등록(즐겨찾기)한 Topic 코드 목록 - Cold Start 폴백 범위를 좁히는 데 씀
def find_user_interested_topics(session: Session, user_id: int) -> list[str]:
    result = session.run(
        "MATCH (:User {userId: $userId})-[:INTERESTED_IN]->(t:Topic) RETURN t.topicCode AS topicCode",
        userId=user_id,
    )
    return [record["topicCode"] for record in result]


# 인기도 폴백 후보 조회 - Event별 소비한 서로 다른 유저 수(인기도 재료)와 발생 시각.
# topic_codes가 주어지면 그 Topic으로 분류된 Event만, 비어있으면(=관심 Topic 없음) 전체 Event 대상.
def find_events_with_consumer_counts(session: Session, topic_codes: list[str]) -> list[dict]:
    result = session.run(
        """
        MATCH (e:Event)
        WHERE e.occurredAt IS NOT NULL
          // topicCodes가 None이면 필터 없이 전체 통과, 아니면 그 Topic으로 분류된 Event만
          AND ($topicCodes IS NULL OR EXISTS {
              (e)-[:CLASSIFIED_AS]->(t:Topic) WHERE t.topicCode IN $topicCodes
          })

        // 소비한 유저 없는 Event도 인기도 0으로 포함시켜야 하니 OPTIONAL MATCH
        OPTIONAL MATCH (e)<-[:CONSUMED]-(consumer:User)
        RETURN e.nodeId AS eventId, count(DISTINCT consumer) AS uniqueConsumers, e.occurredAt AS occurredAt
        // 소비자 수가 전부 0으로 묶여도(서비스 초기) 점수 동점자끼리는 최신순이 유지되도록
        ORDER BY e.occurredAt DESC
        """,
        # 빈 리스트를 그대로 넘기면 Cypher의 `IN []`가 항상 거짓이라 아무것도 안 나옴 -> None으로 바꿔서 "필터 없음"으로 취급
        topicCodes=topic_codes or None,
    )
    return [
        {
            "eventId": record["eventId"],
            "uniqueConsumers": record["uniqueConsumers"],
            "occurredAt": record["occurredAt"].to_native(),
        }
        for record in result
    ]


# 5. POST /internal/v1/recommendations/calculate 응답 조립용
# 유저가 Neo4j User Graph에 존재하는지 확인 - 없는 유저는 추천 계산 대상에서 제외
def user_exists(session: Session, user_id: int) -> bool:
    result = session.run("MATCH (u:User {userId: $userId}) RETURN u LIMIT 1", userId=user_id).single()
    return result is not None


# 최종 추천 Event들의 화면 표시 정보(제목/대표 Topic) 조회 - event_id -> {label, topicCode}
def fetch_event_display_info(session: Session, event_ids: list[str]) -> dict[str, dict]:
    result = session.run(
        """
        MATCH (e:Event) WHERE e.nodeId IN $eventIds
        OPTIONAL MATCH (e)-[:CLASSIFIED_AS]->(t:Topic)
        RETURN e.nodeId AS eventId, e.title AS label, t.topicCode AS topicCode
        """,
        eventIds=event_ids,
    )
    return {record["eventId"]: {"label": record["label"], "topicCode": record["topicCode"]} for record in result}
