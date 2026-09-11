package com.starlightnews.backend.domain.user.controller;

import com.starlightnews.backend.domain.graph.exception.GraphErrorCode;
import com.starlightnews.backend.domain.user.dto.PersonalGraphMapResponse;
import com.starlightnews.backend.domain.user.dto.PersonalGraphSummaryResponse;
import com.starlightnews.backend.domain.user.dto.PersonalNodeArticlesResponse;
import com.starlightnews.backend.domain.user.service.GraphNodeClickService;
import com.starlightnews.backend.domain.user.service.PersonalGraphService;
import com.starlightnews.backend.domain.user.service.PersonalNodeArticleService;
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
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import lombok.RequiredArgsConstructor;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestAttribute;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@Tag(name = "개인 그래프", description = "사용자 지식 그래프 기록 · 조회")
@RestController
@Validated
@RequiredArgsConstructor
@RequestMapping(ApiPaths.API_V1 + "/users/me/graph")
public class UserGraphController {

	private final GraphNodeClickService graphNodeClickService;
	private final PersonalGraphService personalGraphService;
	private final PersonalNodeArticleService personalNodeArticleService;

	@Operation(
			summary = "그래프 Node 클릭 기록",
			description = """
					사용자가 그래프의 Node 를 직접 클릭했을 때 개인 지식 그래프에 클릭 신호를 기록한다. **Access Token 필요.**
					- 대상 nodeType: `EVENT, ENTITY, STATEMENT`
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
			@Parameter(description = "클릭한 Node 유형 (EVENT / ENTITY / STATEMENT)", example = "ENTITY")
			@PathVariable String nodeType,
			@Parameter(description = "Node 의 업무 ID(nodeId)", example = "00000024-0920-4000-8000-000000000001")
			@PathVariable String nodeKey,
			@Parameter(hidden = true) @AuthenticationPrincipal AuthenticatedUser user,
			@Parameter(hidden = true) @RequestAttribute(RequestIdFilter.ATTRIBUTE_NAME) String requestId
	) {
		graphNodeClickService.recordClick(user.userId(), resolvePersonalNodeType(nodeType), nodeKey);
		return ApiResponse.success(null, requestId);
	}

	@Operation(
			summary = "개인 그래프 Topic 스냅샷 조회",
			description = """
					선택한 Topic 의 개인 지식 그래프(내가 읽거나 클릭한 Node)와 그 사이 Edge 를 한 번에 조회한다. **Access Token 필요.**
					- 개인 Node 포함 여부는 MySQL user_knowledge_nodes 기준, Edge 는 Neo4j 조회
					- 반환 Node 유형: `EVENT, ENTITY, STATEMENT`""")
	@ApiResponses({
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "200", description = "조회 성공"),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "400",
					description = "지원하지 않는 topicCode (code: INVALID_TOPIC_CODE)",
					content = @Content(schema = @Schema(implementation = ErrorResponse.class))),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "401",
					description = "Access Token 오류 (code: UNAUTHORIZED / INVALID_ACCESS_TOKEN / EXPIRED_ACCESS_TOKEN)",
					content = @Content(schema = @Schema(implementation = ErrorResponse.class)))
	})
	@GetMapping("/map")
	public ApiResponse<PersonalGraphMapResponse> getTopicMap(
			@Parameter(description = "조회할 개인 그래프의 Topic 코드", example = "ECONOMY")
			@RequestParam String topicCode,
			@Parameter(hidden = true) @AuthenticationPrincipal AuthenticatedUser user,
			@Parameter(hidden = true) @RequestAttribute(RequestIdFilter.ATTRIBUTE_NAME) String requestId
	) {
		return ApiResponse.success(personalGraphService.getTopicMap(user.userId(), topicCode), requestId);
	}

	@Operation(
			summary = "개인 그래프 요약 조회",
			description = """
					내 읽기 최초 진입용 요약 그래프를 조회한다. Topic Cluster 와 각 Topic 의 대표 개인 Node(최대 5개)·Edge 를
					반환한다. **Access Token 필요.**
					- 개인 Node 가 하나도 없으면 `nodes`·`edges` 모두 빈 배열이다""")
	@ApiResponses({
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "200", description = "조회 성공"),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "401",
					description = "Access Token 오류 (code: UNAUTHORIZED / INVALID_ACCESS_TOKEN / EXPIRED_ACCESS_TOKEN)",
					content = @Content(schema = @Schema(implementation = ErrorResponse.class)))
	})
	@GetMapping
	public ApiResponse<PersonalGraphSummaryResponse> getSummary(
			@Parameter(hidden = true) @AuthenticationPrincipal AuthenticatedUser user,
			@Parameter(hidden = true) @RequestAttribute(RequestIdFilter.ATTRIBUTE_NAME) String requestId
	) {
		return ApiResponse.success(personalGraphService.getSummary(user.userId()), requestId);
	}

	@Operation(
			summary = "개인 그래프 노드별 읽은 기사 조회",
			description = """
					개인 그래프에서 선택한 Node 와 관련된 기사 중, 내가 실제로 읽은 기사만 최근 읽은 순으로 조회한다. **Access Token 필요.**
					- 대상 nodeType: `EVENT, ENTITY, STATEMENT`
					- 선택한 Node 가 개인 그래프에 없으면 404""")
	@ApiResponses({
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "200", description = "조회 성공"),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "400",
					description = "지원하지 않는 nodeType(INVALID_NODE_TYPE) / size 범위 위반(INVALID_INPUT_VALUE) / 잘못된 cursor(INVALID_CURSOR)",
					content = @Content(schema = @Schema(implementation = ErrorResponse.class))),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "401",
					description = "Access Token 오류 (code: UNAUTHORIZED / INVALID_ACCESS_TOKEN / EXPIRED_ACCESS_TOKEN)",
					content = @Content(schema = @Schema(implementation = ErrorResponse.class))),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "404",
					description = "개인 그래프에 없는 Node (code: NODE_NOT_ACQUIRED)",
					content = @Content(schema = @Schema(implementation = ErrorResponse.class)))
	})
	@GetMapping("/nodes/{nodeType}/{nodeKey}/articles")
	public ApiResponse<PersonalNodeArticlesResponse> getReadArticles(
			@Parameter(description = "Node 유형 (EVENT / ENTITY / STATEMENT)", example = "ENTITY")
			@PathVariable String nodeType,
			@Parameter(description = "Node 의 업무 ID(nodeId)", example = "00000024-0920-4000-8000-000000000001")
			@PathVariable String nodeKey,
			@Parameter(description = "이번 응답 최대 기사 수 (1~50)", example = "20")
			@RequestParam(defaultValue = "20") @Min(1) @Max(50) int size,
			@Parameter(description = "더 보기 커서 (직전 응답의 nextCursor)")
			@RequestParam(required = false) String cursor,
			@Parameter(hidden = true) @AuthenticationPrincipal AuthenticatedUser user,
			@Parameter(hidden = true) @RequestAttribute(RequestIdFilter.ATTRIBUTE_NAME) String requestId
	) {
		NodeType resolvedType = resolvePersonalNodeType(nodeType);
		return ApiResponse.success(
				personalNodeArticleService.getReadArticles(user.userId(), resolvedType, nodeKey, size, cursor),
				requestId);
	}

	/**
	 * path 의 nodeType 문자열을 개인 그래프 대상 NodeType 으로 변환한다.
	 * 알 수 없는 값이거나 EVENT·ENTITY·STATEMENT 가 아니면 INVALID_NODE_TYPE.
	 * STORY 는 Article 과 직접 관계가 없고 개인 그래프 화면에도 노출하지 않아 대상이 아니다.
	 */
	private NodeType resolvePersonalNodeType(String rawNodeType) {
		NodeType type = NodeType.from(rawNodeType)
				.orElseThrow(() -> new BusinessException(GraphErrorCode.INVALID_NODE_TYPE));
		return switch (type) {
			case EVENT, ENTITY, STATEMENT -> type;
			default -> throw new BusinessException(GraphErrorCode.INVALID_NODE_TYPE);
		};
	}
}
