# Spring Batch가 User Graph 동기화를 요청하는 내부 API.
from fastapi import APIRouter, Depends

from app.database import get_neo4j_session
from app.dependencies import verify_internal_service
from app.user_graph import service
from app.user_graph.schemas import UserGraphSyncRequest

router = APIRouter(dependencies=[Depends(verify_internal_service)])


@router.post("/user-graph/sync")
async def sync_user_graph(request: UserGraphSyncRequest, session=Depends(get_neo4j_session)) -> dict:
    result = service.sync_user_graph(request, session)
    return {"data": result}
