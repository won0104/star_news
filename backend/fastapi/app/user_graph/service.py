# User Graph 동기화 비즈니스 로직
from neo4j import Session

from app.user_graph import repository
from app.user_graph.schemas import UserGraphSyncRequest, UserGraphSyncResult


# 사용자별로 User/관심/비선호/소비 Event를 반영하고, 마지막에 Story Coverage를 재계산한다.
def sync_user_graph(request: UserGraphSyncRequest, session: Session) -> UserGraphSyncResult:
    for user in request.users:
        repository.upsert_user(session, user.user_id, request.aggregated_at)

        node_keys = [node.node_key for node in user.interest_nodes]
        repository.sync_interest_nodes(session, user.user_id, node_keys, request.aggregated_at)

        repository.sync_dislike_topics(session, user.user_id, user.dislike_topic_codes, request.aggregated_at)

        # CONSUMED 반영 -> COVERED는 그 직후에 재계산해야 최신 소비 내역이 반영됨
        consumed_events = [
            {"eventId": event.event_id, "count": event.count, "lastViewedAt": event.last_viewed_at}
            for event in user.consumed_events
        ]
        repository.sync_consumed_events(session, user.user_id, consumed_events, request.aggregated_at)
        repository.refresh_story_coverage(session, user.user_id, request.aggregated_at)

    return UserGraphSyncResult(processed_users=len(request.users), updated_users=len(request.users))
