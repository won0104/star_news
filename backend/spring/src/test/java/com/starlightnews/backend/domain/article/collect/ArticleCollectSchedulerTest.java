package com.starlightnews.backend.domain.article.collect;

import java.time.LocalDateTime;
import java.util.List;

import com.starlightnews.backend.domain.article.dto.CollectedArticle;
import com.starlightnews.backend.domain.article.service.ArticleStoreService;
import com.starlightnews.backend.domain.article.support.ArticleUrls;
import com.starlightnews.backend.global.enums.ContentType;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.verify;

@ExtendWith(MockitoExtension.class)
class ArticleCollectSchedulerTest {

	@Mock
	private ArticleCollectService articleCollectService;

	@Mock
	private ArticleStoreService articleStoreService;

	/** 전처리는 실물을 쓴다. 스케줄러가 수집·전처리·저장을 잇는지 보는 테스트다. */
	private ArticleCollectScheduler scheduler;

	@BeforeEach
	void setUp() {
		scheduler = new ArticleCollectScheduler(
				articleCollectService, new CollectedArticlePreprocessor(), articleStoreService);
	}

	private CollectedArticle article(String url) {
		return new CollectedArticle("제목", url, ArticleUrls.hash(url),
				LocalDateTime.of(2026, 9, 14, 14, 0), "본문입니다. ".repeat(40), ContentType.FULL_TEXT,
				"business", "연합뉴스", "www.yna.co.kr");
	}

	@Test
	void 수집한_기사를_전처리해_저장에_넘긴다() {
		List<CollectedArticle> collected = List.of(
				article("https://news.test/1"), article("https://news.test/2"));
		given(articleCollectService.collectAll()).willReturn(collected);

		scheduler.collect();

		verify(articleStoreService).store(eq(collected));
	}

	@Test
	void 전처리에서_걸러진_기사는_저장에_넘기지_않는다() {
		CollectedArticle kept = article("https://news.test/1");
		CollectedArticle dropped = new CollectedArticle("[인사] 보건복지부", "https://news.test/2",
				ArticleUrls.hash("https://news.test/2"), LocalDateTime.of(2026, 9, 14, 14, 0),
				"본문입니다. ".repeat(40), ContentType.FULL_TEXT, "business", "연합뉴스", "www.yna.co.kr");
		given(articleCollectService.collectAll()).willReturn(List.of(kept, dropped));

		scheduler.collect();

		verify(articleStoreService).store(eq(List.of(kept)));
	}

	@Test
	void 수집_결과가_없어도_저장을_호출한다() {
		// 빈 목록 처리는 저장 쪽이 담당한다. 스케줄러가 분기를 중복으로 갖지 않는다.
		given(articleCollectService.collectAll()).willReturn(List.of());

		scheduler.collect();

		verify(articleStoreService).store(any());
	}
}
