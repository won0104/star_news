package com.starlightnews.backend.domain.demo.dto;

import java.time.LocalDateTime;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

/**
 * 시연용 기사 입력.
 *
 * <p>수집 배치를 거치지 않고 화면에서 직접 붙여넣는 기사다. 제목과 본문만 필수이고, 나머지는
 * 넣지 않으면 시연용 기본값을 쓴다.
 *
 * @param sourceName  언론사 이름. 없으면 "시연"으로 저장한다
 * @param publishedAt KST 벽시계 기준 발행 시각. 없으면 현재 시각을 쓴다
 */
public record DemoArticleRequest(

		@Schema(description = "기사 제목", example = "부산 북항 친수공원에 이틀째 상어 출몰")
		@NotBlank(message = "제목은 필수입니다.")
		@Size(max = 500, message = "제목은 500자를 넘을 수 없습니다.")
		String title,

		@Schema(description = "기사 본문", example = "19일 부산 북항 친수공원 수로에서 상어가 발견됐다. ...")
		@NotBlank(message = "본문은 필수입니다.")
		@Size(min = 100, message = "본문은 100자 이상이어야 분석할 수 있습니다.")
		String content,

		@Schema(description = "언론사 이름", example = "연합뉴스")
		@Size(max = 100, message = "언론사 이름은 100자를 넘을 수 없습니다.")
		String sourceName,

		@Schema(description = "발행 시각(KST). 생략하면 현재 시각", example = "2026-09-23T14:30:00")
		LocalDateTime publishedAt
) {
}
