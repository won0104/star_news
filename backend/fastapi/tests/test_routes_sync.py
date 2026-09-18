import inspect

from app.articles.router import analyze_article
from app.recommendations.router import calculate_recommendations
from app.user_graph.router import sync_user_graph


# 안에서 동기 HTTP·Neo4j 호출을 하므로 async def 면 이벤트 루프가 막혀 다른 요청까지 멈춘다.
# def 로 둬야 FastAPI 가 스레드풀에서 실행한다.
def test_blocking_routes_are_not_coroutines():
    for route in (analyze_article, calculate_recommendations, sync_user_graph):
        assert not inspect.iscoroutinefunction(route), route.__name__
