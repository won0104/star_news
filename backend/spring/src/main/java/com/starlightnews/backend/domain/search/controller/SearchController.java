package com.starlightnews.backend.domain.search.controller;

import com.starlightnews.backend.domain.search.dto.SearchRequest;
import com.starlightnews.backend.domain.search.dto.SearchResultItem;
import com.starlightnews.backend.domain.search.service.SearchService;
import com.starlightnews.backend.global.constant.ApiPaths;
import com.starlightnews.backend.global.error.ErrorResponse;
import com.starlightnews.backend.global.request.RequestIdFilter;
import com.starlightnews.backend.global.response.ApiResponse;
import com.starlightnews.backend.global.response.CursorResponse;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.media.Content;
import io.swagger.v3.oas.annotations.media.Schema;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import io.swagger.v3.oas.annotations.security.SecurityRequirements;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestAttribute;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/**
 * 비회원과 로그인 사용자가 공통으로 사용하는 그래프 Node 검색 API.
 */
@Tag(name = "검색", description = "지식 그래프 Node 검색")
@RestController
@RequiredArgsConstructor
@RequestMapping(ApiPaths.API_V1 + "/search")
public class SearchController {

	private final SearchService searchService;

	@Operation(
			summary = "그래프 Node 검색",
			description = """
					검색어를 정규화해 Event.title, Entity.canonicalName, Statement.text에서 관련 Node를 조회한다.
					완전 일치, 전체 Token 일치, 일부 Token 일치 순으로 정렬하며 내부 점수는 노출하지 않는다.
					검색 결과가 없으면 200과 빈 items 배열을 반환한다. Node 선택 이후에는 공용 Graph API를 사용한다.""")
	@ApiResponses({
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "200", description = "검색 성공"),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "400",
					description = "검색어·size·cursor가 올바르지 않음 (code: INVALID_REQUEST)",
					content = @Content(schema = @Schema(implementation = ErrorResponse.class))),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "500",
					description = "Neo4j 검색 실패 (code: SEARCH_QUERY_FAILED)",
					content = @Content(schema = @Schema(implementation = ErrorResponse.class)))
	})
	@SecurityRequirements
	@GetMapping
	public ApiResponse<CursorResponse<SearchResultItem>> search(
			@Parameter(description = "검색어 또는 문장", example = "한국은행이 금리를 동결했다", required = true)
			@RequestParam(required = false) String query,
			@Parameter(description = "다음 페이지 커서")
			@RequestParam(required = false) String cursor,
			@Parameter(description = "이번 응답 최대 결과 수 (1~50)", example = "20",
					schema = @Schema(type = "integer", defaultValue = "20", minimum = "1", maximum = "50"))
			@RequestParam(defaultValue = "20") String size,
			@Parameter(hidden = true) @RequestAttribute(RequestIdFilter.ATTRIBUTE_NAME) String requestId
	) {
		SearchRequest request = SearchRequest.of(query, cursor, size);
		return ApiResponse.success(searchService.search(request), requestId);
	}
}
