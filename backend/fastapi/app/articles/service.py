# 기사 분석 비즈니스 로직 - AI 분석 결과를 파싱해서 Neo4j에 반영
from datetime import datetime, timezone

from app.articles import repository
from app.articles.schemas import ArticleAnalyzeRequest, ArticleAnalyzeResult
from app.articles.support.entity_filter import normalize_entity_name
from app.articles.support.topic_map import subtopic_code_from_name, topic_code_from_name
from app.exceptions import AppException


# 기사 분석 요청 하나를 처리: AI 호출 -> topic/subtopic 매핑 확인 -> Neo4j 반영(트랜잭션)
def analyze_article(request: ArticleAnalyzeRequest, session) -> ArticleAnalyzeResult:
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
    return session.execute_write(
        lambda tx: _apply_analysis(tx, request, ai_result, primary_topic_code, subtopic_code, now)
    )


# 요청을 AI 입력 형식으로 바꿔서 starlight_ai를 호출하고, 분석 결과(dict)를 그대로 받아온다
# (numpy/torch 등 무거운 의존성이 있어서 실제로 호출하는 시점에만 임포트)
def _call_ai(request: ArticleAnalyzeRequest) -> dict:
    from starlight_ai import process_article

    return process_article(
        {
            "article_id": str(request.article_id),
            "mysql_article_id": request.article_id,
            "title": request.title,
            "content": request.content,
            "published_at": request.published_at.isoformat(),
        }
    )


# AI에서 반환된 nodes[]/edges[]를 순서대로 반영하고 최종 결과를 만든다
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

    # AI가 이번 응답 안에서만 쓰는 임시 nodeId -> 실제로 반영된 Neo4j nodeId
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
    for node in nodes:
        if "Event" in node["labels"]:
            props = node["properties"]
            # 위에서 만든 Entity 이름을 Actor/Target 충돌 판단에 사용
            actor_names = _linked_entity_names(edges, "ACTOR", props["nodeId"], id_map, normalized_name_by_ai_id)
            target_names = _linked_entity_names(edges, "TARGET", props["nodeId"], id_map, normalized_name_by_ai_id)

            real_id = repository.merge_event_node(
                tx, props["title"], props["embedding"], props["embeddingModel"], now, actor_names, target_names
            )
            id_map[props["nodeId"]] = real_id
            event_node_ids.add(real_id)

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

    # Edge 반영
    for edge in edges:
        # consumed면 위에서 이미 반영됨, CLASSIFIED_AS는 classification.topic으로 별도 반영하므로 여기선 건너뜀
        if edge["edgeId"] in consumed_edge_ids or edge["type"] == "CLASSIFIED_AS":
            continue
        start_id = id_map.get(edge["startNodeId"])
        end_id = id_map.get(edge["endNodeId"])

        # 노이즈로 걸러진 Entity 등 실제로 안 만들어진 노드를 참조하는 엣지는 연결할 대상이 없으니 건너뜀
        if start_id is None or end_id is None:
            continue

        edge_props = edge.get("properties", {})
        confidence = edge_props.get("confidence")
        if edge["type"] == "COVERS":
            # COVERS는 isPrimary 처리 때문에 별도 함수(merge_covers_edge)로 뺌
            is_primary = edge_props.get("isPrimary")
            repository.merge_covers_edge(tx, start_id, end_id, confidence, is_primary, now)
        else:
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
