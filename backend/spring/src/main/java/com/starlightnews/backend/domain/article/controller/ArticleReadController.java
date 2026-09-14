package com.starlightnews.backend.domain.article.controller;

import com.starlightnews.backend.domain.user.service.ArticleReadService;
import com.starlightnews.backend.global.constant.ApiPaths;
import com.starlightnews.backend.global.error.ErrorResponse;
import com.starlightnews.backend.global.security.AuthenticatedUser;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.media.Content;
import io.swagger.v3.oas.annotations.media.Schema;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

@Tag(name = "기사 열람", description = "기사 열람 기록 저장 · 갱신")
@RestController
@RequiredArgsConstructor
@RequestMapping(ApiPaths.API_V1 + "/articles")
public class ArticleReadController {

	private final ArticleReadService articleReadService;

	@Operation(
			summary = "기사 열람 기록 저장",
			description = """
					기사 상세 조회가 성공한 뒤 화면 진입 1회당 한 번 호출한다. **Access Token 필요.**
					- 재열람은 새 Row 를 만들지 않고 기존 기록의 열람 횟수·최근 열람 시각만 갱신한다
					- 기사에 연결된 개인 지식 Node(`EVENT, ENTITY, STATEMENT`)를 함께 반영한다
					- 같은 기사를 다시 읽어도 Node 의 고유 열람 기사 수는 늘지 않는다
					- 아직 AI 분석 전인 기사는 열람 기록만 남기고 개인 지식 Node 는 건드리지 않는다
					- 화면 재렌더링이나 요약 상태 polling 으로 중복 호출하지 않는다""")
	@ApiResponses({
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "204",
					description = "기록 성공 (Response Body 없음)"),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "400",
					description = "articleId 형식 오류 (code: TYPE_MISMATCH)",
					content = @Content(schema = @Schema(implementation = ErrorResponse.class))),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "401",
					description = "Access Token 오류 (code: UNAUTHORIZED / INVALID_ACCESS_TOKEN / EXPIRED_ACCESS_TOKEN)",
					content = @Content(schema = @Schema(implementation = ErrorResponse.class))),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "404",
					description = "기사를 찾을 수 없음 (code: RESOURCE_NOT_FOUND)",
					content = @Content(schema = @Schema(implementation = ErrorResponse.class)))
	})
	@PostMapping("/{articleId}/reads")
	@ResponseStatus(HttpStatus.NO_CONTENT)
	public void recordArticleRead(
			@Parameter(description = "열람한 기사 ID", example = "930001")
			@PathVariable Long articleId,
			@Parameter(hidden = true) @AuthenticationPrincipal AuthenticatedUser user
	) {
		articleReadService.recordRead(user.userId(), articleId);
	}
}
