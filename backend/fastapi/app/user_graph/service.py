# User Graph 동기화 비즈니스 로직
from neo4j import Session

from app.exceptions import AppException
from app.user_graph import repository
from app.user_graph.schemas import UserGraphSyncRequest, UserGraphSyncResult


# 사용자별로 User/관심/비선호/소비 Event를 반영하고, Story Coverage를 재계산
def sync_user_graph(request: UserGraphSyncRequest, session: Session) -> UserGraphSyncResult:
    updated_count = sum(_sync_single_user(user, request.aggregated_at, session) for user in request.users)

    # 요청받은 사용자 전원이 stale이라 아무도 반영 안 됐으면 이 회차 전체를 stale로 취급
    if updated_count == 0 and request.users:
        raise AppException(409, "STALE_USER_GRAPH_SNAPSHOT", "더 최신 스냅샷이 이미 반영되어 있습니다.")

    return UserGraphSyncResult(processed_users=len(request.users), updated_users=updated_count)


# 사용자 한 명의 User Graph를 반영
def _sync_single_user(user, aggregated_at, session: Session) -> bool:
    # 이미 최신 스냅샷이 반영돼 있으면 건너뛰고 False를 반환
    current_updated_at = repository.get_user_updated_at(session, user.user_id)
    if current_updated_at is not None and current_updated_at >= aggregated_at:
        return False

    # User 노드 생성/갱신
    repository.upsert_user(session, user.user_id, aggregated_at)

    # 관심 Node(Entity/Topic/Story) 반영
    node_keys = [node.node_key for node in user.interest_nodes]
    matched_interests = repository.sync_interest_nodes(session, user.user_id, node_keys, aggregated_at)

    # 비선호 Topic 반영
    matched_dislikes = repository.sync_dislike_topics(
        session, user.user_id, user.dislike_topic_codes, aggregated_at
    )

    # 소비 Event 반영
    consumed_payload = [
        {
            "eventId": event.event_id,
            "count": event.count,
            "lastViewedAt": event.last_viewed_at,
            "eventFavorited": event.event_favorited,
        }
        for event in user.consumed_events
    ]
    matched_events = repository.sync_consumed_events(session, user.user_id, consumed_payload, aggregated_at)

    # 위 세 반영이 요청한 개수만큼 실제로 매칭됐는지 검증 (안 맞으면 404)
    _validate_all_references_found(user, matched_interests, matched_dislikes, matched_events)

    # Story Coverage 재계산
    repository.refresh_story_coverage(session, user.user_id, aggregated_at)

    return True


# 요청한 참조(관심 Node/비선호 Topic/소비 Event)가 실제로 다 Neo4j에 존재했는지 검증
def _validate_all_references_found(user, matched_interests: int, matched_dislikes: int, matched_events: int) -> None:
    if matched_interests != len(user.interest_nodes):
        raise AppException(404, "GRAPH_REFERENCE_NOT_FOUND", "존재하지 않는 관심 Node가 포함되어 있습니다.")
    if matched_dislikes != len(user.dislike_topic_codes):
        raise AppException(404, "GRAPH_REFERENCE_NOT_FOUND", "존재하지 않는 비선호 Topic이 포함되어 있습니다.")
    if matched_events != len(user.consumed_events):
        raise AppException(404, "GRAPH_REFERENCE_NOT_FOUND", "존재하지 않는 소비 Event가 포함되어 있습니다.")
