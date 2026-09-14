package com.starlightnews.backend.domain.user.service;

import java.time.LocalDateTime;

import com.starlightnews.backend.domain.article.repository.ArticleRepository;
import com.starlightnews.backend.domain.user.domain.ArticleRead;
import com.starlightnews.backend.domain.user.domain.ArticleReadId;
import com.starlightnews.backend.domain.user.repository.ArticleReadRepository;
import com.starlightnews.backend.global.error.BusinessException;
import com.starlightnews.backend.global.error.CommonErrorCode;
import com.starlightnews.backend.global.error.ErrorCode;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.dao.DataIntegrityViolationException;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.catchThrowable;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;

@ExtendWith(MockitoExtension.class)
class ArticleReadServiceTest {

	@Mock
	private ArticleReadRepository articleReadRepository;

	@Mock
	private ArticleRepository articleRepository;

	@InjectMocks
	private ArticleReadService articleReadService;

	private static final long USER_ID = 1L;
	private static final long ARTICLE_ID = 101L;

	private ErrorCode errorCodeOf(Throwable throwable) {
		assertThat(throwable).isInstanceOf(BusinessException.class);
		return ((BusinessException) throwable).getErrorCode();
	}

	@Test
	void 기존_Row가_있으면_incrementRead만_하고_최초_열람이_아니다() {
		given(articleRepository.existsById(ARTICLE_ID)).willReturn(true);
		given(articleReadRepository.incrementRead(any(), any())).willReturn(1);

		boolean firstRead = articleReadService.recordRead(USER_ID, ARTICLE_ID);

		assertThat(firstRead).isFalse();
		verify(articleReadRepository).incrementRead(
				eq(new ArticleReadId(USER_ID, ARTICLE_ID)), any(LocalDateTime.class));
		verify(articleReadRepository, never()).save(any());
	}

	@Test
	void Row가_없으면_click_count_1인_새_Row를_만들고_최초_열람이다() {
		given(articleRepository.existsById(ARTICLE_ID)).willReturn(true);
		given(articleReadRepository.incrementRead(any(), any())).willReturn(0);

		boolean firstRead = articleReadService.recordRead(USER_ID, ARTICLE_ID);

		assertThat(firstRead).isTrue();
		ArgumentCaptor<ArticleRead> captor = ArgumentCaptor.forClass(ArticleRead.class);
		verify(articleReadRepository).save(captor.capture());
		ArticleRead saved = captor.getValue();
		assertThat(saved.getId()).isEqualTo(new ArticleReadId(USER_ID, ARTICLE_ID));
		assertThat(saved.getClickCount()).isEqualTo(1);
		assertThat(saved.getFirstReadAt()).isEqualTo(saved.getLastReadAt());
	}

	@Test
	void 없는_기사면_RESOURCE_NOT_FOUND이고_저장하지_않는다() {
		given(articleRepository.existsById(ARTICLE_ID)).willReturn(false);

		Throwable thrown = catchThrowable(() -> articleReadService.recordRead(USER_ID, ARTICLE_ID));

		assertThat(errorCodeOf(thrown)).isEqualTo(CommonErrorCode.RESOURCE_NOT_FOUND);
		verify(articleReadRepository, never()).incrementRead(any(), any());
		verify(articleReadRepository, never()).save(any());
	}

	@Test
	void 첫_열람_동시_요청으로_save가_충돌하면_incrementRead로_되돌리고_최초_열람이_아니다() {
		given(articleRepository.existsById(ARTICLE_ID)).willReturn(true);
		given(articleReadRepository.incrementRead(any(), any())).willReturn(0, 1);
		given(articleReadRepository.save(any()))
				.willThrow(new DataIntegrityViolationException("duplicate key"));

		boolean firstRead = articleReadService.recordRead(USER_ID, ARTICLE_ID);

		assertThat(firstRead).isFalse();
		verify(articleReadRepository, times(2)).incrementRead(any(), any());
	}
}
