"""실제 뉴스 데이터 + 실제 로컬 AI 모델 + 실제 로컬 Neo4j로 Story 임계값을 검증하는 수동 실험.

로컬 GPU/모델/Neo4j가 필요해서 CI/배포 환경에는 절대 안 돌게 항상 skip 처리함.
실제로 돌리려면 본문 주석을 전부 풀고, 아래 환경변수를 채운 뒤 RUN_MANUAL_AI_VALIDATION=1로 실행:
    KG_MODEL_DIR, HF_CACHE_DIR, ARTICLES_JSONL_PATH
"""
from __future__ import annotations

import json
import os

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_MANUAL_AI_VALIDATION") != "1",
    reason="로컬 AI 모델 + 로컬 Neo4j가 필요한 수동 실험 - CI/배포 환경에서는 skip",
)

# 관련 있어 보이는 기사 묶음 + 통제군(무관한 기사) - 실제 검증 때 쓴 샘플 그대로 유지
SELECTED_IDS = [
    5005003, 5005004,
    5005005, 5005006,
    5005119, 5005122, 5005160,
    5005141, 5005143, 5005145,
    5005147, 5005150,
    5005113, 5005117, 5005138,
    5005007, 5005167,
    5005114, 5005134, 5005176, 5005180,
]


def _load_articles(path: str, ids: list[int]) -> list[dict]:
    wanted = set(ids)
    by_id = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            if row["articleId"] in wanted:
                by_id[row["articleId"]] = row
    return sorted(by_id.values(), key=lambda r: r["publishedAt"])


def test_story_clustering_against_real_articles():
    # 아래는 실제로 돌릴 때만 주석 해제할 것 (import sys, Path, datetime, neo4j, starlight_ai,
    # app.* 전부 이 파일 상단이 아니라 여기 안에서만 import해서 skip될 땐 아무 영향 없음)
    pass
    # import sys
    # from datetime import datetime
    # from pathlib import Path
    #
    # # ai/starlight_ai는 이 repo의 형제 디렉토리(backend/fastapi가 아니라 ai/)에 있음
    # ai_root = Path(__file__).resolve().parents[4] / "ai"
    # sys.path.insert(0, str(ai_root))
    #
    # from neo4j import GraphDatabase
    # from starlight_ai import ArticleAnalyzer
    #
    # from app.articles import service
    # from app.articles.schemas import ArticleAnalyzeRequest
    # from app.config import settings
    #
    # articles = _load_articles(os.environ["ARTICLES_JSONL_PATH"], SELECTED_IDS)
    #
    # analyzer = ArticleAnalyzer(
    #     device="cpu",
    #     kg_dir=os.environ["KG_MODEL_DIR"],
    #     hf_cache=os.environ["HF_CACHE_DIR"],
    #     local_files_only=True,
    # )
    #
    # # 실제 HTTP 호출(_call_ai) 대신 로컬 ArticleAnalyzer를 직접 태워서 실제 AI 결과로 검증
    # def _fake_call_ai(request: ArticleAnalyzeRequest) -> dict:
    #     return analyzer.process({
    #         "article_id": str(request.article_id),
    #         "mysql_article_id": request.article_id,
    #         "title": request.title,
    #         "content": request.content,
    #         "published_at": request.published_at.isoformat(),
    #     })
    #
    # service._call_ai = _fake_call_ai
    #
    # driver = GraphDatabase.driver(settings.neo4j_uri, auth=(settings.neo4j_username, settings.neo4j_password))
    # with driver.session() as session:
    #     for art in articles:
    #         request = ArticleAnalyzeRequest(
    #             article_id=art["articleId"],
    #             title=art["title"],
    #             content=art["content"],
    #             source_id=1,
    #             source_name="실험용 언론사",
    #             published_at=datetime.fromisoformat(art["publishedAt"]),
    #         )
    #         service.analyze_article(request, session)
    #
    #     # Event 하나가 서로 다른 Story 두 개에 동시에 속하면 안 됨 (과거 발견한 실제 버그 재발 감지용)
    #     dup = session.run(
    #         """
    #         MATCH (a:Article)-[:COVERS]->(e:Event)-[:PART_OF]->(s:Story)
    #         WHERE a.mysqlArticleId IN $ids
    #         WITH DISTINCT e, s
    #         WITH e, collect(DISTINCT s.nodeId) AS storyIds
    #         WHERE size(storyIds) > 1
    #         RETURN count(e) AS n
    #         """,
    #         ids=SELECTED_IDS,
    #     ).single()["n"]
    #     assert dup == 0
