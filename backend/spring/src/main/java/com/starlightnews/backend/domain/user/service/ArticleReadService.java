package com.starlightnews.backend.domain.user.service;

import java.time.LocalDateTime;

import com.starlightnews.backend.domain.article.repository.ArticleRepository;
import com.starlightnews.backend.domain.user.domain.ArticleRead;
import com.starlightnews.backend.domain.user.domain.ArticleReadId;
import com.starlightnews.backend.domain.user.repository.ArticleReadRepository;
import com.starlightnews.backend.global.error.BusinessException;
import com.starlightnews.backend.global.error.CommonErrorCode;
import lombok.RequiredArgsConstructor;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * 기사 상세 화면 진입 1회를 article_reads 에 기록한다.
 * 갱신을 먼저 시도하고(재열람이 hot path 라 UPDATE 한 번), 대상 Row 가 없을 때만 새 Row 를 만든다.
 */
@Service
@RequiredArgsConstructor
public class ArticleReadService {

	private final ArticleReadRepository articleReadRepository;
	private final ArticleRepository articleRepository;

	/**
	 * 열람 기록을 저장하거나 갱신한다.
	 *
	 * @return 이 사용자가 해당 기사를 처음 읽은 것이면 true.
	 *         개인 지식 Node 의 고유 열람 기사 수(read_article_count)를 올릴지 가르는 값이다.
	 */
	@Transactional
	public boolean recordRead(Long userId, Long articleId) {
		if (!articleRepository.existsById(articleId)) {
			throw new BusinessException(CommonErrorCode.RESOURCE_NOT_FOUND);
		}

		ArticleReadId id = new ArticleReadId(userId, articleId);
		LocalDateTime now = LocalDateTime.now();

		if (articleReadRepository.incrementRead(id, now) == 1) {
			return false;
		}

		try {
			articleReadRepository.save(ArticleRead.forFirstRead(id, now));
			return true;
		} catch (DataIntegrityViolationException concurrentInsert) {
			// 동시 첫 열람으로 다른 요청이 먼저 Row 를 만든 경우: 이제 존재하므로 갱신으로 되돌린다.
			// 최초 열람은 먼저 INSERT 한 쪽이 가져가므로 이 요청은 재열람으로 본다.
			articleReadRepository.incrementRead(id, now);
			return false;
		}
	}
}
