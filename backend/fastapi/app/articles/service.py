# 기사 분석 비즈니스 로직 - AI 분석 결과를 파싱해서 Neo4j에 반영
from datetime import datetime, timezone

import httpx

from app.articles import repository
from app.articles.schemas import ArticleAnalyzeRequest, ArticleAnalyzeResult
from app.articles.support.entity_filter import normalize_entity_name
from app.articles.support.topic_map import subtopic_code_from_name, topic_code_from_name
from app.config import settings
from app.exceptions import AppException


# 기사 분석 요청 하나를 처리: AI 호출 -> topic/subtopic 매핑 확인 -> Neo4j 반영(트랜잭션)
def analyze_article(request: ArticleAnalyzeRequest, session) -> ArticleAnalyzeResult:
    # Spring이 타임아웃으로 포기한 뒤 재시도해도, 이전 요청이 이미 커밋까지 끝났으면 AI를 또 부르지 않고 저장된 값을 그대로 돌려준다
    existing = repository.find_completed_analysis(session, request.article_id)
    if existing is not None:
        return ArticleAnalyzeResult(
            article_id=request.article_id,
            article_node_id=existing["nodeId"],
            status="COMPLETED",
            primary_topic_code=existing["topicCode"],
            subtopic_code=existing["subtopicCode"],
        )

    ai_result = _call_ai(request)
    classification = ai_result["classification"]
    ai_topic = classification.get("topic")

    primary_topic_code = topic_code_from_name(ai_topic)
    if primary_topic_code is None:
        raise AppException(500, "EXTRACTION_FAILED", f"매핑되지 않은 topic 라벨: {ai_topic!r}")

    ai_small_cls = classification.get("small_cls")
    subtopic_code = subtopic_code_from_name(ai_small_cls)
    if subtopic_code is None:
        raise AppException(500, "EXTRACTION_FAILED", f"매핑되지 않은 subtopic 라벨: {ai_small_cls!r}")

    now = datetime.now(timezone.utc)

    # 중간에 실패해도 이 기사에서 만든 노드가 하나도 안 남도록, 아래 반영을 전부 트랜잭션 하나로 묶는다
    try:
        return session.execute_write(
            lambda tx: _apply_analysis(tx, request, ai_result, primary_topic_code, subtopic_code, now)
        )
    except repository.ArticleIdentityConflictError as exc:
        # 과거 오프라인 번들의 가짜 mysqlArticleId와 실제 MySQL PK가 겹친 경우다.
        # 기존 레거시 Article을 운영 기사로 덮지 않고 트랜잭션 전체를 중단한다.
        raise AppException(
            409,
            "ARTICLE_IDENTITY_CONFLICT",
            "기존 그래프 Article의 식별자가 운영 UUID 정책과 충돌합니다.",
        ) from exc


# FastAPI 컨테이너는 torch/모델을 갖지 않는다.
# 여기서는 기사 정보를 AI 워커에 보내고 분석 JSON만 받아온다. 덕분에 FastAPI가
# 재배포되어도 AI 워커의 프로세스와 메모리에 올라간 모델은 그대로 유지된다.
def _call_ai(request: ArticleAnalyzeRequest) -> dict:
    payload = {
        "article_id": str(request.article_id),
        "mysql_article_id": request.article_id,
        "title": request.title,
        "content": request.content,
        "published_at": request.published_at.isoformat(),
    }
    endpoint = f"{settings.ai_base_url.rstrip('/')}/internal/v1/articles/analyze"
    # 연결 실패는 빠르게 감지하되, CPU 추론 시간은 별도의 긴 read timeout으로 허용한다.
    timeout = httpx.Timeout(
        settings.ai_request_timeout_seconds,
        connect=settings.ai_connect_timeout_seconds,
    )

    try:
        response = httpx.post(endpoint, json=payload, timeout=timeout)
    except httpx.TimeoutException as exc:
        # 연결에는 성공했지만 정해진 시간 안에 기사 분석이 끝나지 않은 경우다.
        raise AppException(504, "EXTRACTION_FAILED", "AI 분석 시간이 초과되었습니다.") from exc
    except httpx.RequestError as exc:
        # DNS, 연결 거절 등 AI 워커 자체에 도달하지 못한 경우다.
        raise AppException(503, "EXTRACTION_FAILED", "AI 분석 서비스에 연결할 수 없습니다.") from exc

    # AI가 기사 입력 자체를 거부한 경우만 사용자의 요청 오류로 돌려준다.
    # 그 밖의 AI 오류는 FastAPI 뒤쪽 서비스의 실패이므로 502로 구분한다.
    if response.status_code == 400:
        raise AppException(400, "INVALID_ARTICLE", _ai_error_message(response))
    if response.status_code >= 400:
        raise AppException(502, "EXTRACTION_FAILED", "AI 분석 서비스가 추론에 실패했습니다.")

    try:
        result = response.json()
    except ValueError as exc:
        raise AppException(502, "EXTRACTION_FAILED", "AI 분석 응답을 읽을 수 없습니다.") from exc

    # 저장 로직이 요구하는 최소 계약을 입구에서 검증해 부분 적재를 방지한다.
    if (
        not isinstance(result, dict)
        or not isinstance(result.get("classification"), dict)
        or not isinstance(result.get("nodes"), list)
        or not isinstance(result.get("edges"), list)
    ):
        raise AppException(502, "EXTRACTION_FAILED", "AI 분석 응답 형식이 올바르지 않습니다.")
    return result


def _ai_error_message(response: httpx.Response) -> str:
    """Read the worker's safe validation message without trusting its body shape."""
    try:
        detail = response.json().get("detail")
    except (ValueError, AttributeError):
        detail = None
    return str(detail) if detail else "분석할 기사 내용이 올바르지 않습니다."


# AI의 임시 그래프를 실제 Neo4j 그래프로 옮기는 함수다.
# 노드를 먼저 생성해야 엣지 양 끝의 실제 ID를 알 수 있음.
# Article → Time/Entity → Event → Statement → Edge 순서를 꼭 지키셈.
def _apply_analysis(
    tx,
    request: ArticleAnalyzeRequest,
    ai_result: dict,
    primary_topic_code: str,
    subtopic_code: str,
    now: datetime,
) -> ArticleAnalyzeResult:
    nodes = ai_result.get("nodes", [])
    edges = ai_result.get("edges", [])

    # AI 응답의 nodeId는 이번 응답 안에서만 유효하다.
    # 각 노드를 MERGE하면서 얻은 실제 Neo4j nodeId를 저장해 두었다가 엣지 생성 때 사용한다.
    id_map: dict[str, str | None] = {}

    # Article 노드 반영
    article_node_id = repository.merge_article_node(
        tx, request.article_id, request.title, request.published_at, subtopic_code, now
    )
    article_ai_node = _find_node(nodes, "Article")
    if article_ai_node:
        id_map[article_ai_node["properties"]["nodeId"]] = article_node_id

    # Time 노드 반영
    for node in nodes:
        if "Time" in node["labels"]:
            props = node["properties"]
            id_map[props["nodeId"]] = repository.merge_time_node(tx, props["timeKey"], props["granularity"], now)

    # Entity 노드 반영
    normalized_name_by_ai_id: dict[str, str] = {} # Event의 Actor/Target 판단에 쓸 정규화된 이름
    for node in nodes:
        if "Entity" in node["labels"]:
            props = node["properties"]
            id_map[props["nodeId"]] = repository.merge_extracted_entity(tx, props["canonicalName"], props["entityType"], now)
            normalized_name_by_ai_id[props["nodeId"]] = normalize_entity_name(props["canonicalName"])

    # Event 노드 반영
    event_node_ids: set[str] = set()
    # 이 기사 안에서 먼저 처리한 Event/Story들 - 벡터 인덱스가 같은 트랜잭션의 미커밋 쓰기를 못 보는 사각지대가 있어서(실측으로 확인함)
    events_in_this_article: list[dict] = []
    stories_in_this_article: list[dict] = []
    orphans_in_this_article: list[dict] = []
    for node in nodes:
        if "Event" in node["labels"]:
            props = node["properties"]
            # 위에서 만든 Entity 이름을 Actor/Target 충돌 판단에 사용
            actor_names = _linked_entity_names(edges, "ACTOR", props["nodeId"], id_map, normalized_name_by_ai_id)
            target_names = _linked_entity_names(edges, "TARGET", props["nodeId"], id_map, normalized_name_by_ai_id)

            real_id, is_new_event = repository.merge_event_node(
                tx, props["title"], props["embedding"], props["embeddingModel"],
                request.published_at, now, actor_names, target_names, events_in_this_article
            )
            id_map[props["nodeId"]] = real_id
            event_node_ids.add(real_id)
            events_in_this_article.append({
                "nodeId": real_id, "embedding": props["embedding"],
                "actorNames": actor_names, "targetNames": target_names,
            })

            # Story 배정은 Event가 새로 생겼을 때 한 번만
            if is_new_event:
                repository.assign_event_to_story(
                    tx, real_id, props["title"], props["embedding"], props["embeddingModel"],
                    primary_topic_code, request.published_at, now, actor_names, target_names,
                    stories_in_this_article, orphans_in_this_article,
                )

    # Statement 노드 반영
    statement_node_ids: set[str] = set()
    consumed_edge_ids: set[str] = set()
    for node in nodes:
        if "Statement" in node["labels"]:
            props = node["properties"]
            edge = _find_edge(edges, "CONTAINS_STATEMENT", end_node_id=props["nodeId"])
            confidence = edge["properties"].get("confidence") if edge else None

            real_id = repository.merge_statement_node(
                tx, article_node_id, props["text"], props["statementType"], confidence, now
            )

            id_map[props["nodeId"]] = real_id
            statement_node_ids.add(real_id)

            if edge:
                # merge_statement_node가 이 엣지를 이미 만들었으니, 아래 엣지 루프에서 또 안 만들게 표시
                consumed_edge_ids.add(edge["edgeId"])

    # COVERS는 AI 임시 Event 여러 개가 같은 실제 Event로 병합될 수 있으므로
    # 실제 UUID 매핑 후 중복 제거한다. 모델은 primary를 주지 않으므로 안정적인
    # Event UUID 순서의 첫 관계 하나만 primary로 정한다.
    covers_by_event: dict[str, float | None] = {}
    for edge in edges:
        if edge["type"] != "COVERS":
            continue
        start_id = id_map.get(edge["startNodeId"])
        end_id = id_map.get(edge["endNodeId"])
        if start_id != article_node_id or end_id is None:
            continue
        confidence = (edge.get("properties") or {}).get("confidence")
        previous = covers_by_event.get(end_id)
        if previous is None or (confidence is not None and confidence > previous):
            covers_by_event[end_id] = confidence

    if not covers_by_event:
        raise AppException(502, "EXTRACTION_FAILED", "분석 결과에 유효한 COVERS 관계가 없습니다.")

    # 재분석 전에 과거 primary를 모두 해제해야 이전 Event가 더 이상 결과에 없어도
    # primary=true 관계가 두 개 이상 남지 않는다.
    repository.reset_covers_primary(tx, article_node_id)
    for index, event_id in enumerate(sorted(covers_by_event)):
        repository.merge_covers_edge(
            tx,
            article_node_id,
            event_id,
            covers_by_event[event_id],
            index == 0,
            now,
        )

    # 나머지 Edge 반영: 앞 단계에서 노드들의 실제 ID가 모두 id_map에 등록된 뒤 실행한다.
    for edge in edges:
        # consumed면 위에서 이미 반영됨, CLASSIFIED_AS는 classification.topic으로 별도 반영하므로 여기선 건너뜀
        if (
            edge["edgeId"] in consumed_edge_ids
            or edge["type"] in {"CLASSIFIED_AS", "COVERS"}
        ):
            continue
        start_id = id_map.get(edge["startNodeId"])
        end_id = id_map.get(edge["endNodeId"])

        # 노이즈 Entity처럼 저장 단계에서 제외된 노드는 실제 ID가 없다.
        # 이 노드를 가리키는 엣지도 연결할 대상이 없으므로 함께 건너뛴다.
        if start_id is None or end_id is None:
            continue

        edge_props = edge.get("properties", {})
        confidence = edge_props.get("confidence")
        repository.merge_simple_edge(tx, edge["type"], start_id, end_id, confidence, now)

    # Topic 분류 - Article은 AI 분류 그대로, Event/Statement는 Article의 대분류를 상속
    repository.classify_article(tx, article_node_id, primary_topic_code, now)
    for node_id in event_node_ids | statement_node_ids:
        repository.inherit_classification_from_article(tx, node_id, primary_topic_code, now)

    # PUBLISHED_BY - Spring이 준 언론사 정보로 직접 반영
    news_org_node_id = repository.merge_news_organization_entity(tx, request.source_id, request.source_name, now) # 없으면 생성, 있으면 재사용
    repository.merge_published_by_edge(tx, article_node_id, news_org_node_id, now) # 노드에 연결

    return ArticleAnalyzeResult(
        article_id=request.article_id,
        article_node_id=article_node_id,
        status="COMPLETED",
        primary_topic_code=primary_topic_code,
        subtopic_code=subtopic_code,
    )


# nodes[]에서 특정 label을 가진 첫 노드를 찾는다
def _find_node(nodes: list[dict], label: str) -> dict | None:
    return next((n for n in nodes if label in n["labels"]), None)


# edges[]에서 특정 타입 + 도착 노드로 향하는 엣지 하나를 찾는다
def _find_edge(edges: list[dict], edge_type: str, end_node_id: str) -> dict | None:
    return next((e for e in edges if e["type"] == edge_type and e["endNodeId"] == end_node_id), None)


# start_ai_id에서 나가는 edge_type 엣지를 따라가서, 실제로 만들어진 Entity의 정규화된 이름만 모은다
def _linked_entity_names(
    edges: list[dict],
    edge_type: str,
    start_ai_id: str,
    id_map: dict[str, str | None],
    normalized_name_by_ai_id: dict[str, str],
) -> list[str]:
    names = []
    for edge in edges:
        # 이 Event에서 나가는, 원하는 타입(ACTOR/TARGET)의 엣지만 본다
        if edge["type"] != edge_type or edge["startNodeId"] != start_ai_id:
            continue
        entity_ai_id = edge["endNodeId"]
        # 노이즈로 걸러져서 실제로 안 만들어진 Entity면 이름 목록에 넣을 게 없으니 건너뜀
        if id_map.get(entity_ai_id) is None:
            continue
        # 살아남은 Entity면 미리 저장해둔 정규화된 이름을 꺼내서 담는다
        name = normalized_name_by_ai_id.get(entity_ai_id)
        if name:
            names.append(name)
    return names
