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


# 기사 하나 분석 완료 결과
class ArticleAnalyzeResult(CamelModel):
    article_id: int
    article_node_id: str  # Neo4j Article.nodeId (MySQL articles.node_id에 채울 값)
    status: str
    primary_topic_code: str
    subtopic_code: str
