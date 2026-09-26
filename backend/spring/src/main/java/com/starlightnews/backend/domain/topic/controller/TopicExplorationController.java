package com.starlightnews.backend.domain.topic.controller;

import com.starlightnews.backend.domain.topic.dto.TopicExplorationResponse;
import com.starlightnews.backend.domain.topic.service.TopicExplorationService;
import com.starlightnews.backend.global.constant.ApiPaths;
import com.starlightnews.backend.global.error.ErrorResponse;
import com.starlightnews.backend.global.request.RequestIdFilter;
import com.starlightnews.backend.global.response.ApiResponse;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.media.Content;
import io.swagger.v3.oas.annotations.media.Schema;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import io.swagger.v3.oas.annotations.security.SecurityRequirements;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestAttribute;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * 비회원과 로그인 사용자가 공통으로 사용하는 Topic별 탐색 진입 Node 조회 API.
 */
@Tag(name = "토픽")
@RestController
@RequiredArgsConstructor
@RequestMapping(ApiPaths.API_V1 + "/topics")
public class TopicExplorationController {

	private final TopicExplorationService topicExplorationService;

	@Operation(
			summary = "Topic별 탐색 진입 Node 조회",
			description = """
					선택한 Topic을 중심으로 탐색 화면에 표시할 대표 Event를 순위순으로 최대 10개 반환한다.
					05:50/17:50 KST 기준으로 집계한 결과를 06:00/18:00부터 조회한다.
					중심 Topic은 표시용이며 Event 순위에 포함하지 않는다.
					공개된 결과가 없으면 snapshotAt은 null, entryNodes는 빈 배열이다.
					요청 시 집계하거나 Neo4j·개인화 정보를 조회하지 않는다.""")
	@ApiResponses({
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "200", description = "조회 성공"),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "400",
					description = "지원하지 않는 Topic 코드 (INVALID_TOPIC_CODE)",
					content = @Content(schema = @Schema(implementation = ErrorResponse.class))),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "500",
					description = "Topic별 탐색 데이터 조회 또는 조합 실패 (TOPIC_EXPLORATION_FETCH_FAILED)",
					content = @Content(schema = @Schema(implementation = ErrorResponse.class)))
	})
	@SecurityRequirements
	@GetMapping("/{topicCode}/exploration")
	public ApiResponse<TopicExplorationResponse> getTopicExploration(
			@Parameter(
					description = "조회할 Topic 코드",
					example = "ECONOMY",
					required = true)
			@PathVariable String topicCode,
			@Parameter(hidden = true)
			@RequestAttribute(RequestIdFilter.ATTRIBUTE_NAME) String requestId
	) {
		return ApiResponse.success(topicExplorationService.getTopicExploration(topicCode), requestId);
	}
}
