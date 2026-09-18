from datetime import datetime, timedelta, timezone

from app.articles.schemas import ArticleAnalyzeRequest

KST = timezone(timedelta(hours=9))


def _request(published_at: str) -> ArticleAnalyzeRequest:
    return ArticleAnalyzeRequest.model_validate({
        "articleId": 1,
        "title": "제목",
        "content": "본문",
        "sourceId": 1,
        "sourceName": "연합뉴스",
        "publishedAt": published_at,
    })


# 시간대 없이 오면 Neo4j 에 LOCAL DATETIME 으로 저장돼 시간대 있는 값과 섞인다.
def test_naive_published_at_is_treated_as_kst():
    published_at = _request("2026-09-17T10:33:23").published_at

    assert published_at.utcoffset() == timedelta(hours=9)
    assert published_at == datetime(2026, 9, 17, 10, 33, 23, tzinfo=KST)


def test_published_at_with_offset_is_kept():
    published_at = _request("2026-09-17T10:33:23+09:00").published_at

    assert published_at == datetime(2026, 9, 17, 10, 33, 23, tzinfo=KST)


# 다른 시간대로 와도 시각을 바꾸지 않는다. 같은 순간이면 Neo4j 비교·정렬은 맞다.
def test_published_at_in_other_offset_is_not_shifted():
    published_at = _request("2026-09-17T01:33:23Z").published_at

    assert published_at.utcoffset() == timedelta(0)
    assert published_at == datetime(2026, 9, 17, 10, 33, 23, tzinfo=KST)
