package com.starlightnews.backend.domain.article.service;

import java.util.Optional;

import com.starlightnews.backend.domain.article.repository.NewsOrganizationRepository;
import com.starlightnews.backend.global.error.BusinessException;
import com.starlightnews.backend.global.error.CommonErrorCode;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * 수집한 기사의 언론사를 news_organizations 의 ID 로 바꾼다. 없으면 만든다.
 *
 * <p>식별 키는 도메인이다. 제공처가 언론사명 자리에 도메인 문자열을 주는 경우가 있어 이름은 믿을 수 없고,
 * 도메인으로 묶어두면 나중에 표시명이 틀린 걸 발견해도 name 만 UPDATE 하면 된다.
 * 도메인이 없는 기사는 이름으로 식별한다.
 */
@Service
@RequiredArgsConstructor
public class NewsOrganizationResolver {

	private final NewsOrganizationRepository newsOrganizationRepository;

	/**
	 * @param domain 언론사 홈 도메인. 제공처가 주지 않으면 null
	 * @return 언론사 ID
	 */
	@Transactional
	public Long resolveId(String name, String domain) {
		if (name == null || name.isBlank()) {
			throw new BusinessException(CommonErrorCode.INVALID_INPUT_VALUE);
		}

		// 잠금을 잡지 않는 조회로 먼저 본다. 대부분은 이미 있는 언론사라 여기서 끝난다.
		Optional<Long> existing = findExisting(name, domain);
		if (existing.isPresent()) {
			return existing.get();
		}

		newsOrganizationRepository.insertIfAbsent(name, domain);

		// 위 INSERT 가 무시됐다면 그 사이 다른 스레드가 만들었거나, 같은 이름이 다른 도메인으로 이미 있다.
		// 이름이 같으면 같은 언론사로 본다 — 한 언론사가 도메인을 여러 개 쓰는 경우다.
		return findExisting(name, domain)
				.orElseThrow(() -> new BusinessException(CommonErrorCode.INTERNAL_SERVER_ERROR));
	}

	private Optional<Long> findExisting(String name, String domain) {
		if (domain != null && !domain.isBlank()) {
			Optional<Long> byDomain = newsOrganizationRepository.findIdByDomain(domain);
			if (byDomain.isPresent()) {
				return byDomain;
			}
		}
		return newsOrganizationRepository.findIdByName(name);
	}
}
