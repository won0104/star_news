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
    event_click_count: int
    last_viewed_at: datetime
    event_favorited: bool = False


class UserGraphSyncUser(CamelModel):
    user_id: int
    interest_nodes: list[InterestNode]
    dislike_topic_codes: list[str]
    consumed_events: list[ConsumedEvent]


class UserGraphSyncRequest(CamelModel):
    users: list[UserGraphSyncUser]
    aggregated_at: datetime


# 유저 한 명 동기화 실패 - Spring이 이 유저만 따로 추적/재시도할 수 있게 이유(code)를 같이 줌
class UserGraphSyncFailure(CamelModel):
    user_id: int
    code: str


class UserGraphSyncResult(CamelModel):
    processed_users: int
    updated_users: int
    failed: list[UserGraphSyncFailure] = []
