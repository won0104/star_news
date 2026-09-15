package com.starlightnews.backend.domain.article.service;

import java.time.LocalDateTime;
import java.util.List;

import com.starlightnews.backend.domain.article.dto.CollectedArticle;
import com.starlightnews.backend.domain.article.support.ArticleUrls;
import com.starlightnews.backend.global.enums.ContentType;
import com.starlightnews.backend.global.error.BusinessException;
import com.starlightnews.backend.global.error.CommonErrorCode;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;

@ExtendWith(MockitoExtension.class)
class ArticleStoreServiceTest {

	@Mock
	private ArticleWriter articleWriter;

	@InjectMocks
	private ArticleStoreService articleStoreService;

	private CollectedArticle article(String url) {
		return new CollectedArticle("제목", url, ArticleUrls.hash(url),
				LocalDateTime.of(2026, 9, 14, 14, 0), "본문", ContentType.FULL_TEXT,
				"business", "연합뉴스", "www.yna.co.kr");
	}

	@Test
	void 모든_기사를_저장하고_신규_건수를_반환한다() {
		given(articleWriter.write(any())).willReturn(true);

		int stored = articleStoreService.store(
				List.of(article("https://news.test/1"), article("https://news.test/2")));

		assertThat(stored).isEqualTo(2);
		verify(articleWriter, times(2)).write(any());
	}

	@Test
	void 이미_있던_기사는_신규로_세지_않는다() {
		given(articleWriter.write(any())).willReturn(true, false);

		int stored = articleStoreService.store(
				List.of(article("https://news.test/1"), article("https://news.test/2")));

		assertThat(stored).isEqualTo(1);
	}

	@Test
	void 한_건이_실패해도_나머지를_저장한다() {
		// 한 건 때문에 회차 전체를 버리면 다음 주기까지 아무것도 안 쌓인다.
		given(articleWriter.write(any()))
				.willThrow(new BusinessException(CommonErrorCode.INTERNAL_SERVER_ERROR))
				.willReturn(true);

		int stored = articleStoreService.store(
				List.of(article("https://news.test/1"), article("https://news.test/2")));

		assertThat(stored).isEqualTo(1);
		verify(articleWriter, times(2)).write(any());
	}

	@Test
	void 모두_실패해도_예외를_밖으로_던지지_않는다() {
		// 스케줄러가 죽으면 다음 회차도 안 돈다. 실패는 로그로 남기고 회차를 정상 종료한다.
		given(articleWriter.write(any())).willThrow(new RuntimeException("DB 장애"));

		assertThat(articleStoreService.store(List.of(article("https://news.test/1")))).isZero();
	}

	@Test
	void 수집_결과가_없으면_아무것도_하지_않는다() {
		assertThat(articleStoreService.store(List.of())).isZero();
		verifyNoInteractions(articleWriter);
	}
}
