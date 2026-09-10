package com.starlightnews.backend.domain.user.controller;

import com.starlightnews.backend.domain.graph.exception.GraphErrorCode;
import com.starlightnews.backend.domain.user.service.GraphNodeClickService;
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
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestAttribute;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@Tag(name = "개인 그래프", description = "사용자 지식 그래프 기록 · 조회")
@RestController
@RequiredArgsConstructor
@RequestMapping(ApiPaths.API_V1 + "/users/me/graph")
public class UserGraphController {

	private final GraphNodeClickService graphNodeClickService;

	@Operation(
			summary = "그래프 Node 클릭 기록",
			description = """
					사용자가 그래프의 Node 를 직접 클릭했을 때 개인 지식 그래프에 클릭 신호를 기록한다. **Access Token 필요.**
					- 대상 nodeType: `EVENT, STORY, ENTITY, STATEMENT`
					- Node 상세 조회(GET) 는 클릭으로 치지 않으며, 실제 클릭 이벤트에서만 호출한다
					- 이미 기록된 Node 면 클릭 수만 +1, 처음이면 새 Row 를 만든다""")
	@ApiResponses({
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "200",
					description = "기록 성공 (data: null)"),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "400",
					description = "지원하지 않는 nodeType (code: INVALID_NODE_TYPE)",
					content = @Content(schema = @Schema(implementation = ErrorResponse.class))),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "401",
					description = "Access Token 오류 (code: UNAUTHORIZED / INVALID_ACCESS_TOKEN / EXPIRED_ACCESS_TOKEN)",
					content = @Content(schema = @Schema(implementation = ErrorResponse.class))),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "404",
					description = "Neo4j 에서 Node 를 찾을 수 없음 (code: RESOURCE_NOT_FOUND)",
					content = @Content(schema = @Schema(implementation = ErrorResponse.class)))
	})
	@PostMapping("/nodes/{nodeType}/{nodeKey}/clicks")
	public ApiResponse<Void> recordNodeClick(
			@Parameter(description = "클릭한 Node 유형 (EVENT / STORY / ENTITY / STATEMENT)", example = "ENTITY")
			@PathVariable String nodeType,
			@Parameter(description = "Node 의 업무 ID(nodeId)", example = "00000024-0920-4000-8000-000000000001")
			@PathVariable String nodeKey,
			@Parameter(hidden = true) @AuthenticationPrincipal AuthenticatedUser user,
			@Parameter(hidden = true) @RequestAttribute(RequestIdFilter.ATTRIBUTE_NAME) String requestId
	) {
		graphNodeClickService.recordClick(user.userId(), resolvePersonalNodeType(nodeType), nodeKey);
		return ApiResponse.success(null, requestId);
	}

	/**
	 * path 의 nodeType 문자열을 개인 그래프 대상 NodeType 으로 변환한다.
	 * 알 수 없는 값이거나 EVENT·STORY·ENTITY·STATEMENT 가 아니면 INVALID_NODE_TYPE.
	 */
	private NodeType resolvePersonalNodeType(String rawNodeType) {
		NodeType type = NodeType.from(rawNodeType)
				.orElseThrow(() -> new BusinessException(GraphErrorCode.INVALID_NODE_TYPE));
		return switch (type) {
			case EVENT, STORY, ENTITY, STATEMENT -> type;
			default -> throw new BusinessException(GraphErrorCode.INVALID_NODE_TYPE);
		};
	}
}
