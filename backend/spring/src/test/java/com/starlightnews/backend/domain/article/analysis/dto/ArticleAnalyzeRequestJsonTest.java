package com.starlightnews.backend.domain.article.analysis.dto;

import java.time.LocalDateTime;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.json.JsonTest;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * 운영과 같은 ObjectMapper 로 분석 요청을 직렬화해 본다.
 *
 * <p>클라이언트 테스트는 직접 만든 ObjectMapper 로 돈다. 운영 설정(예: spring.jackson.time-zone)이
 * 날짜를 다르게 쓰면 거기서는 드러나지 않는다.
 */
@JsonTest
class ArticleAnalyzeRequestJsonTest {

	@Autowired
	private ObjectMapper objectMapper;

	@Test
	void 발행_시각을_KST_오프셋이_붙은_문자열로_쓴다() throws Exception {
		ArticleAnalyzeRequest request = ArticleAnalyzeRequest.of(930001L, "제목", "본문",
				940010L, "연합뉴스", LocalDateTime.of(2026, 9, 16, 9, 30));

		String json = objectMapper.writeValueAsString(request);

		assertThat(json).contains("\"publishedAt\":\"2026-09-16T09:30:00+09:00\"");
	}

	@Test
	void 필드_이름이_FastAPI_계약과_같다() throws Exception {
		String json = objectMapper.writeValueAsString(ArticleAnalyzeRequest.of(930001L, "제목", "본문",
				940010L, "연합뉴스", LocalDateTime.of(2026, 9, 16, 9, 30)));

		assertThat(json).contains("\"articleId\":930001", "\"title\":", "\"content\":",
				"\"sourceId\":940010", "\"sourceName\":", "\"publishedAt\":");
	}
}
