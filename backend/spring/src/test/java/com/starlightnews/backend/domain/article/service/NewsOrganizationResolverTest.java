package com.starlightnews.backend.domain.article.service;

import java.util.Optional;

import com.starlightnews.backend.domain.article.repository.NewsOrganizationRepository;
import com.starlightnews.backend.global.error.BusinessException;
import com.starlightnews.backend.global.error.CommonErrorCode;
import com.starlightnews.backend.global.error.ErrorCode;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.catchThrowable;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;

@ExtendWith(MockitoExtension.class)
class NewsOrganizationResolverTest {

	@Mock
	private NewsOrganizationRepository newsOrganizationRepository;

	@InjectMocks
	private NewsOrganizationResolver resolver;

	private ErrorCode errorCodeOf(Throwable thrown) {
		assertThat(thrown).isInstanceOf(BusinessException.class);
		return ((BusinessException) thrown).getErrorCode();
	}

	@Test
	void 도메인으로_이미_있는_언론사를_찾으면_그대로_쓴다() {
		given(newsOrganizationRepository.findIdByDomain("www.yna.co.kr")).willReturn(Optional.of(7L));

		assertThat(resolver.resolveId("연합뉴스", "www.yna.co.kr")).isEqualTo(7L);
		verify(newsOrganizationRepository, never()).insertIfAbsent(any(), any());
	}

	@Test
	void 표시명이_달라도_도메인이_같으면_같은_언론사로_본다() {
		// 제공처가 언론사명 자리에 도메인 문자열을 주는 경우가 있어 이름은 믿지 않는다.
		given(newsOrganizationRepository.findIdByDomain("www.yna.co.kr")).willReturn(Optional.of(7L));

		assertThat(resolver.resolveId("yna.co.kr", "www.yna.co.kr")).isEqualTo(7L);
	}

	@Test
	void 없으면_새로_만들고_ID를_돌려준다() {
		given(newsOrganizationRepository.findIdByDomain("www.yna.co.kr"))
				.willReturn(Optional.empty(), Optional.of(9L));
		given(newsOrganizationRepository.findIdByName("연합뉴스")).willReturn(Optional.empty());

		assertThat(resolver.resolveId("연합뉴스", "www.yna.co.kr")).isEqualTo(9L);
		verify(newsOrganizationRepository).insertIfAbsent("연합뉴스", "www.yna.co.kr");
	}

	@Test
	void 도메인이_없으면_이름으로_식별한다() {
		given(newsOrganizationRepository.findIdByName("이름만 있는 매체")).willReturn(Optional.of(3L));

		assertThat(resolver.resolveId("이름만 있는 매체", null)).isEqualTo(3L);
		verify(newsOrganizationRepository, never()).findIdByDomain(any());
	}

	@Test
	void 같은_이름이_다른_도메인으로_이미_있으면_그_언론사를_쓴다() {
		// name UNIQUE 때문에 INSERT 가 무시된다. 이름이 같으면 도메인을 여러 개 쓰는 같은 언론사로 본다.
		given(newsOrganizationRepository.findIdByDomain("m.yna.co.kr")).willReturn(Optional.empty());
		given(newsOrganizationRepository.findIdByName("연합뉴스"))
				.willReturn(Optional.empty(), Optional.of(7L));

		assertThat(resolver.resolveId("연합뉴스", "m.yna.co.kr")).isEqualTo(7L);
	}

	@Test
	void 이름이_없으면_INVALID_INPUT_VALUE() {
		// organization_id 가 NOT NULL 이라 언론사를 특정할 수 없으면 기사를 저장할 수 없다.
		Throwable thrown = catchThrowable(() -> resolver.resolveId("  ", "www.yna.co.kr"));

		assertThat(errorCodeOf(thrown)).isEqualTo(CommonErrorCode.INVALID_INPUT_VALUE);
		verifyNoInteractions(newsOrganizationRepository);
	}

	@Test
	void INSERT_후에도_찾지_못하면_INTERNAL_SERVER_ERROR() {
		given(newsOrganizationRepository.findIdByDomain(eq("www.yna.co.kr"))).willReturn(Optional.empty());
		given(newsOrganizationRepository.findIdByName("연합뉴스")).willReturn(Optional.empty());

		Throwable thrown = catchThrowable(() -> resolver.resolveId("연합뉴스", "www.yna.co.kr"));

		assertThat(errorCodeOf(thrown)).isEqualTo(CommonErrorCode.INTERNAL_SERVER_ERROR);
	}
}
