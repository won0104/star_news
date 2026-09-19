# Spring Batch가 User Graph 동기화를 요청하는 내부 API.
from fastapi import APIRouter, Depends

from app.database import get_neo4j_session
from app.dependencies import verify_internal_service
from app.user_graph import service
from app.user_graph.schemas import UserGraphSyncRequest

router = APIRouter(dependencies=[Depends(verify_internal_service)])

# 안의 Neo4j 호출이 동기라 async def 가 아닌 def 로 둔다. async def 면 처리 중 이벤트 루프가 막혀
# 다른 요청까지 멈춘다. def 는 FastAPI 가 스레드풀에서 실행한다.


@router.post("/user-graph/sync")
def sync_user_graph(request: UserGraphSyncRequest, session=Depends(get_neo4j_session)) -> dict:
    result = service.sync_user_graph(request, session)
    return {"data": result}
