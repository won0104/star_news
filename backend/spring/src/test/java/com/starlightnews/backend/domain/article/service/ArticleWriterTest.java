package com.starlightnews.backend.domain.article.service;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;

import com.starlightnews.backend.domain.article.dto.CollectedArticle;
import com.starlightnews.backend.domain.article.repository.ArticleRepository;
import com.starlightnews.backend.domain.article.support.ArticleContents;
import com.starlightnews.backend.domain.article.support.ArticleUrls;
import com.starlightnews.backend.global.enums.AnalysisStatus;
import com.starlightnews.backend.global.enums.ContentType;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;

@ExtendWith(MockitoExtension.class)
class ArticleWriterTest {

	@Mock
	private NewsOrganizationResolver newsOrganizationResolver;

	@Mock
	private ArticleRepository articleRepository;

	@InjectMocks
	private ArticleWriter articleWriter;

	private static final String URL = "https://www.yna.co.kr/view/AKR20260914";

	private CollectedArticle article() {
		return new CollectedArticle("기준금리 동결", URL, ArticleUrls.hash(URL),
				LocalDateTime.of(2026, 9, 14, 14, 0), "본문입니다.", ContentType.FULL_TEXT,
				"business", "연합뉴스", "www.yna.co.kr");
	}

	@Test
	void 언론사를_해석해_기사를_저장한다() {
		given(newsOrganizationResolver.resolveId("연합뉴스", "www.yna.co.kr")).willReturn(7L);
		given(articleRepository.findIdByUrlHash(any())).willReturn(Optional.empty());

		boolean stored = articleWriter.write(article());

		assertThat(stored).isTrue();
		verify(articleRepository).insertIfAbsent(eq(7L), eq("기준금리 동결"), eq(URL),
				eq(ArticleUrls.hash(URL)), eq(LocalDateTime.of(2026, 9, 14, 14, 0)),
				eq("business"), eq("본문입니다."), eq(ContentType.FULL_TEXT.name()),
				eq(ArticleContents.hash("본문입니다.")), eq(AnalysisStatus.PROCESSING.name()));
	}

	@Test
	void 수집_직후에는_분석_전_상태로_저장한다() {
		given(newsOrganizationResolver.resolveId(any(), any())).willReturn(7L);
		given(articleRepository.findIdByUrlHash(any())).willReturn(Optional.empty());

		articleWriter.write(article());

		// 분석 단계가 PROCESSING 인 기사를 대상으로 고른다.
		verify(articleRepository).insertIfAbsent(any(), any(), any(), any(), any(), any(), any(),
				any(), any(), eq(AnalysisStatus.PROCESSING.name()));
	}

	@Test
	void 같은_본문이_다른_제목으로_저장돼_있으면_저장하지_않는다() {
		// 사이트의 추천 기사 목록이 본문 자리에 들어오면 제목만 다른 기사가 계속 쌓인다.
		given(articleRepository.findTitlesByContentHash(any()))
				.willReturn(List.of("전혀 다른 제목"));

		assertThat(articleWriter.write(article())).isFalse();

		verify(articleRepository, never()).insertIfAbsent(any(), any(), any(), any(), any(), any(),
				any(), any(), any(), any());
	}

	@Test
	void 같은_본문이_같은_제목으로_저장돼_있으면_저장한다() {
		// 통신사 기사를 여러 매체가 그대로 실은 경우다. 기사 자체는 정상이다.
		given(newsOrganizationResolver.resolveId(any(), any())).willReturn(7L);
		given(articleRepository.findTitlesByContentHash(any()))
				.willReturn(List.of("기준금리 동결"));
		given(articleRepository.findIdByUrlHash(any())).willReturn(Optional.empty());

		assertThat(articleWriter.write(article())).isTrue();
	}

	@Test
	void 이미_저장된_기사면_false를_반환한다() {
		given(newsOrganizationResolver.resolveId(any(), any())).willReturn(7L);
		given(articleRepository.findIdByUrlHash(any())).willReturn(Optional.of(42L));

		assertThat(articleWriter.write(article())).isFalse();
	}

	@Test
	void 이미_저장된_기사여도_Upsert를_호출한다() {
		// 조회와 INSERT 사이에 다른 요청이 끼어들 수 있어 존재 확인은 신규 여부 판단용일 뿐이다.
		// 실제 중복 차단은 url_hash UNIQUE 와 Upsert 가 담당한다.
		given(newsOrganizationResolver.resolveId(any(), any())).willReturn(7L);
		given(articleRepository.findIdByUrlHash(any())).willReturn(Optional.of(42L));

		articleWriter.write(article());

		verify(articleRepository).insertIfAbsent(any(), any(), any(), any(), any(), any(), any(),
				any(), any(), any());
	}
}
