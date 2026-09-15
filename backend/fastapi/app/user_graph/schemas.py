# POST /internal/v1/user-graph/sync 요청/응답 스키마
from datetime import datetime

from app.base_schema import CamelModel


# INTERESTED_IN 관계로 반영할 대상 (Entity/Topic/Story). 점수 없이 존재 여부만 표현
class InterestNode(CamelModel):
    node_type: str
    node_key: str


# CONSUMED 관계로 반영할 Event별 소비 집계
class ConsumedEvent(CamelModel):
    event_id: str
    count: int
    last_viewed_at: datetime
    # Spring이 아직 이 필드를 안 보내도 요청이 깨지지 않게 기본값을 둠 (모르면 즐겨찾기 안 한 것으로 취급)
    event_favorited: bool = False


class UserGraphSyncUser(CamelModel):
    user_id: int
    interest_nodes: list[InterestNode]
    dislike_topic_codes: list[str]
    consumed_events: list[ConsumedEvent]


class UserGraphSyncRequest(CamelModel):
    users: list[UserGraphSyncUser]
    aggregated_at: datetime


class UserGraphSyncResult(CamelModel):
    processed_users: int
    updated_users: int
