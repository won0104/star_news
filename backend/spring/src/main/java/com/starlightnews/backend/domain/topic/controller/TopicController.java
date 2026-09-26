package com.starlightnews.backend.domain.topic.controller;

import com.starlightnews.backend.domain.topic.dto.TopicListResponse;
import com.starlightnews.backend.domain.topic.service.TopicService;
import com.starlightnews.backend.global.constant.ApiPaths;
import com.starlightnews.backend.global.request.RequestIdFilter;
import com.starlightnews.backend.global.response.ApiResponse;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import io.swagger.v3.oas.annotations.security.SecurityRequirements;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestAttribute;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@Tag(name = "토픽", description = "토픽 목록 및 토픽별 탐색")
@RestController
@RequiredArgsConstructor
@RequestMapping(ApiPaths.API_V1 + "/topics")
public class TopicController {

	private final TopicService topicService;

	@Operation(summary = "전체 토픽 목록 조회",
			description = "회원가입과 사용자 설정에서 선택 가능한 토픽 코드와 한글 표시명을 Enum 선언 순서로 반환한다. 인증은 필요하지 않다.")
	@ApiResponses({
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "200", description = "조회 성공")
	})
	@SecurityRequirements
	@GetMapping
	public ApiResponse<TopicListResponse> getTopics(
			@Parameter(hidden = true) @RequestAttribute(RequestIdFilter.ATTRIBUTE_NAME) String requestId
	) {
		return ApiResponse.success(topicService.getTopics(), requestId);
	}
}
