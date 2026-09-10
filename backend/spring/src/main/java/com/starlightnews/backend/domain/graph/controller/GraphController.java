package com.starlightnews.backend.domain.graph.controller;

import com.starlightnews.backend.domain.graph.dto.GraphNodeDetailResponse;
import com.starlightnews.backend.domain.graph.exception.GraphErrorCode;
import com.starlightnews.backend.domain.graph.service.GraphNodeService;
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
import lombok.RequiredArgsConstructor;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestAttribute;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@Tag(name = "그래프", description = "공용 지식 그래프 조회")
@RestController
@RequiredArgsConstructor
@RequestMapping(ApiPaths.API_V1 + "/graphs")
public class GraphController {

	private final GraphNodeService graphNodeService;

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
		NodeType resolvedType = resolveDetailNodeType(nodeType);
		Long userId = (user != null) ? user.userId() : null;
		return ApiResponse.success(graphNodeService.getNodeDetail(resolvedType, nodeKey, userId), requestId);
	}

	/**
	 * path 의 nodeType 문자열을 상세 조회 대상 NodeType 으로 변환한다.
	 * 알 수 없는 값이거나 상세 조회 범위가 아닌 ARTICLE 이면 INVALID_NODE_TYPE.
	 */
	private NodeType resolveDetailNodeType(String rawNodeType) {
		NodeType type = NodeType.from(rawNodeType)
				.orElseThrow(() -> new BusinessException(GraphErrorCode.INVALID_NODE_TYPE));
		if (type == NodeType.ARTICLE) {
			throw new BusinessException(GraphErrorCode.INVALID_NODE_TYPE);
		}
		return type;
	}
}
