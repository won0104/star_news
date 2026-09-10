package com.starlightnews.backend.domain.graph.controller;

import com.starlightnews.backend.domain.graph.dto.GraphNeighborsResponse;
import com.starlightnews.backend.domain.graph.dto.GraphNodeDetailResponse;
import com.starlightnews.backend.domain.graph.dto.RelatedArticlesResponse;
import com.starlightnews.backend.domain.graph.exception.GraphErrorCode;
import com.starlightnews.backend.domain.graph.service.GraphArticleService;
import com.starlightnews.backend.domain.graph.service.GraphNeighborService;
import com.starlightnews.backend.domain.graph.service.GraphNodeService;
import com.starlightnews.backend.domain.graph.support.ArticleRelation;
import com.starlightnews.backend.global.constant.ApiPaths;
import com.starlightnews.backend.global.enums.NodeType;
import com.starlightnews.backend.global.error.BusinessException;
import com.starlightnews.backend.global.error.ErrorResponse;
import com.starlightnews.backend.global.request.RequestIdFilter;
import com.starlightnews.backend.global.response.ApiResponse;
import com.starlightnews.backend.global.security.AuthenticatedUser;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.media.Content;
import io.swagger.v3.oas.annotations.media.Schema;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import io.swagger.v3.oas.annotations.security.SecurityRequirements;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import lombok.RequiredArgsConstructor;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestAttribute;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@Tag(name = "그래프", description = "공용 지식 그래프 조회")
@RestController
@Validated
@RequiredArgsConstructor
@RequestMapping(ApiPaths.API_V1 + "/graphs")
public class GraphController {

	private final GraphNodeService graphNodeService;
	private final GraphArticleService graphArticleService;
	private final GraphNeighborService graphNeighborService;

	@Operation(
			summary = "그래프 Node 상세 조회",
			description = """
					선택한 그래프 Node 의 화면 표시 정보(title·type·time)를 조회한다. 인증 불필요.
					유효한 Access Token 이 있으면 해당 사용자의 즐겨찾기 여부(bookmarked)를 함께 반환하고, 비로그인이면 false.

					- 대상 nodeType: `EVENT, STORY, ENTITY, TOPIC, STATEMENT, TIME` (`ARTICLE` 및 그 외는 `INVALID_NODE_TYPE`)
					- nodeKey: Neo4j 내부 ID 가 아닌 Node 의 업무 ID(nodeId, UUID)
					""")
	@ApiResponses({
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "200", description = "조회 성공"),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "400",
					description = "지원하지 않는 nodeType (code: INVALID_NODE_TYPE)",
					content = @Content(schema = @Schema(implementation = ErrorResponse.class))),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "404",
					description = "Node 를 찾을 수 없음 (code: RESOURCE_NOT_FOUND)",
					content = @Content(schema = @Schema(implementation = ErrorResponse.class))),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "500",
					description = "그래프 Node 조회 실패 (code: GRAPH_NODE_QUERY_FAILED)",
					content = @Content(schema = @Schema(implementation = ErrorResponse.class)))
	})
	@SecurityRequirements
	@GetMapping("/nodes/{nodeType}/{nodeKey}")
	public ApiResponse<GraphNodeDetailResponse> getNodeDetail(
			@Parameter(description = "Node 유형", example = "EVENT")
			@PathVariable String nodeType,
			@Parameter(description = "Node 의 업무 ID(nodeId)", example = "00000020-0920-4000-8000-000000000001")
			@PathVariable String nodeKey,
			@Parameter(hidden = true) @AuthenticationPrincipal AuthenticatedUser user,
			@Parameter(hidden = true) @RequestAttribute(RequestIdFilter.ATTRIBUTE_NAME) String requestId
	) {
		NodeType resolvedType = resolveGraphNodeType(nodeType);
		Long userId = (user != null) ? user.userId() : null;
		return ApiResponse.success(graphNodeService.getNodeDetail(resolvedType, nodeKey, userId), requestId);
	}

	@Operation(
			summary = "그래프 Node 관련 기사 조회",
			description = """
					선택한 Node 와 관련된 기사 목록을 최신 발행 순으로 조회한다. 인증 불필요.
					- 페이지네이션: 첫 요청은 `cursor` 없이, 이후에는 직전 응답의 `nextCursor` 를 `cursor` 로 그대로 전달
					- 기사 전문·요약·원문 URL 은 기사 상세 API 에서 반환한다""")
	@ApiResponses({
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "200", description = "조회 성공"),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "400",
					description = "size 범위 위반(code: INVALID_INPUT_VALUE) / 지원하지 않는 nodeType(INVALID_NODE_TYPE) / 잘못된 cursor(INVALID_CURSOR)",
					content = @Content(schema = @Schema(implementation = ErrorResponse.class))),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "404",
					description = "Node 를 찾을 수 없음 (code: RESOURCE_NOT_FOUND)",
					content = @Content(schema = @Schema(implementation = ErrorResponse.class))),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "500",
					description = "관련 기사 조회 실패 (code: GRAPH_NODE_QUERY_FAILED)",
					content = @Content(schema = @Schema(implementation = ErrorResponse.class)))
	})
	@SecurityRequirements
	@GetMapping("/nodes/{nodeType}/{nodeKey}/articles")
	public ApiResponse<RelatedArticlesResponse> getRelatedArticles(
			@Parameter(description = "Node 유형 (EVENT / ENTITY / STATEMENT)", example = "EVENT")
			@PathVariable String nodeType,
			@Parameter(description = "Node 의 업무 ID(nodeId)", example = "00000020-0920-4000-8000-000000000001")
			@PathVariable String nodeKey,
			@Parameter(description = "이번 응답 최대 기사 수 (1~30)", example = "30")
			@RequestParam(defaultValue = "30") @Min(1) @Max(30) int size,
			@Parameter(description = "더 보기 커서 (직전 응답의 nextCursor)")
			@RequestParam(required = false) String cursor,
			@Parameter(hidden = true) @AuthenticationPrincipal AuthenticatedUser user,
			@Parameter(hidden = true) @RequestAttribute(RequestIdFilter.ATTRIBUTE_NAME) String requestId
	) {
		NodeType resolvedType = resolveArticleNodeType(nodeType);
		Long userId = (user != null) ? user.userId() : null;
		return ApiResponse.success(
				graphArticleService.getRelatedArticles(resolvedType, nodeKey, size, cursor, userId), requestId);
	}

	@Operation(
			summary = "그래프 Node 주변 그래프 조회",
			description = """
					중심 Node 를 기준으로 depth Hop 이내의 주변 Node 와 그 사이 Edge 를 조회한다. 인증 불필요.
					- 반환 Node 유형: `EVENT, STORY, ENTITY, STATEMENT` (`ARTICLE, TOPIC, TIME` 등은 반환·경유 제외)
					- 내부 neighborScore 높은 순 정렬, 커서 페이지네이션
					- 첫 요청은 `cursor` 없이, 이후에는 직전 응답의 `nextCursor` 를 `cursor` 로 그대로 전달""")
	@ApiResponses({
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "200", description = "조회 성공"),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "400",
					description = "지원하지 않는 nodeType(INVALID_NODE_TYPE) / depth·limit 범위 위반(INVALID_INPUT_VALUE) / 잘못된 cursor(INVALID_CURSOR)",
					content = @Content(schema = @Schema(implementation = ErrorResponse.class))),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "404",
					description = "중심 Node 를 찾을 수 없음 (code: RESOURCE_NOT_FOUND)",
					content = @Content(schema = @Schema(implementation = ErrorResponse.class))),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "500",
					description = "주변 그래프 조회 실패 (code: GRAPH_NODE_QUERY_FAILED)",
					content = @Content(schema = @Schema(implementation = ErrorResponse.class)))
	})
	@SecurityRequirements
	@GetMapping("/nodes/{nodeType}/{nodeKey}/neighbors")
	public ApiResponse<GraphNeighborsResponse> getNeighbors(
			@Parameter(description = "중심 Node 유형", example = "ENTITY")
			@PathVariable String nodeType,
			@Parameter(description = "Node 의 업무 ID(nodeId)", example = "00000024-0920-4000-8000-000000000001")
			@PathVariable String nodeKey,
			@Parameter(description = "탐색할 최대 Hop 수 (1~3)", example = "1")
			@RequestParam(defaultValue = "1") @Min(1) @Max(3) int depth,
			@Parameter(description = "중심 Node 를 제외한 최대 주변 Node 수 (1~30)", example = "15")
			@RequestParam(defaultValue = "15") @Min(1) @Max(30) int limit,
			@Parameter(description = "더 보기 커서 (직전 응답의 nextCursor)")
			@RequestParam(required = false) String cursor,
			@Parameter(hidden = true) @RequestAttribute(RequestIdFilter.ATTRIBUTE_NAME) String requestId
	) {
		NodeType resolvedType = resolveGraphNodeType(nodeType);
		return ApiResponse.success(
				graphNeighborService.getNeighbors(resolvedType, nodeKey, depth, limit, cursor), requestId);
	}

	/**
	 * path 의 nodeType 문자열을 공용 그래프 조회 대상 NodeType 으로 변환한다.
	 * 알 수 없는 값이거나 그래프 조회 범위가 아닌 ARTICLE 이면 INVALID_NODE_TYPE.
	 */
	private NodeType resolveGraphNodeType(String rawNodeType) {
		NodeType type = NodeType.from(rawNodeType)
				.orElseThrow(() -> new BusinessException(GraphErrorCode.INVALID_NODE_TYPE));
		if (type == NodeType.ARTICLE) {
			throw new BusinessException(GraphErrorCode.INVALID_NODE_TYPE);
		}
		return type;
	}

	/**
	 * path 의 nodeType 문자열을 관련 기사 조회 대상 NodeType 으로 변환한다.
	 * 알 수 없는 값이거나 EVENT·ENTITY·STATEMENT 가 아니면 INVALID_NODE_TYPE.
	 */
	private NodeType resolveArticleNodeType(String rawNodeType) {
		NodeType type = NodeType.from(rawNodeType)
				.orElseThrow(() -> new BusinessException(GraphErrorCode.INVALID_NODE_TYPE));
		if (ArticleRelation.forNodeType(type).isEmpty()) {
			throw new BusinessException(GraphErrorCode.INVALID_NODE_TYPE);
		}
		return type;
	}
}
