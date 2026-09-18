# POST /internal/v1/articles/analyze 요청/응답 스키마
from datetime import datetime, timedelta, timezone

from pydantic import field_validator

from app.base_schema import CamelModel

# 서비스 기준 시간대. 발행 시각에 시간대가 없으면 이 시간대로 본다.
KST = timezone(timedelta(hours=9), "KST")


# Spring이 기사 분석을 요청할 때 보내는 기사 원문 + 메타
class ArticleAnalyzeRequest(CamelModel):
    article_id: int  # (articleId는 MySQL articles.article_id)
    title: str
    content: str
    source_id: int # 언론사 id (MySQL news_organizations.organization_id)
    source_name: str
    published_at: datetime

    # 시간대 없는 발행 시각은 KST 로 본다.
    # 그대로 두면 Neo4j 에 LOCAL DATETIME 으로 저장되고, 시간대가 있는 값과 섞여 정렬·비교가 깨진다.
    # Spring 은 ZONED DATETIME 으로만 읽어서 이런 기사가 하나라도 걸리면 관련 기사 조회가 실패했다.
    @field_validator("published_at")
    @classmethod
    def _assume_kst_when_naive(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            return value.replace(tzinfo=KST)
        return value


# 기사 하나 분석 완료 결과
class ArticleAnalyzeResult(CamelModel):
    article_id: int
    article_node_id: str  # Neo4j Article.nodeId (MySQL articles.node_id에 채울 값)
    status: str
    primary_topic_code: str
    subtopic_code: str
