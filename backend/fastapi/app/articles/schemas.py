# POST /internal/v1/articles/analyze 요청/응답 스키마
from datetime import datetime

from app.base_schema import CamelModel


# Spring이 기사 분석을 요청할 때 보내는 기사 원문 + 메타
class ArticleAnalyzeRequest(CamelModel):
    article_id: int  # (articleId는 MySQL articles.article_id)
    title: str
    content: str
    source_id: int # 언론사 id (MySQL news_organizations.organization_id)
    source_name: str
    published_at: datetime


# 이번 요청으로 생성/갱신된 Event/Story/Entity/Statement 노드 id 목록
class ArticleAnalyzeNodeIds(CamelModel):
    event_ids: list[str] = []
    story_ids: list[str] = []
    entity_ids: list[str] = []
    statement_ids: list[str] = []


# Spring의 Redis 그래프 캐시 무효화 대상 하나
class AffectedNodeKey(CamelModel):
    node_type: str
    node_id: str


# 기사 하나 분석 완료 결과
class ArticleAnalyzeResult(CamelModel):
    article_id: int
    status: str
    primary_topic_code: str
    subtopic_code: str
    node_ids: ArticleAnalyzeNodeIds
    affected_node_keys: list[AffectedNodeKey]
