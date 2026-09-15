package com.starlightnews.backend.domain.article.service;

import com.starlightnews.backend.domain.article.dto.CollectedArticle;
import com.starlightnews.backend.domain.article.repository.ArticleRepository;
import com.starlightnews.backend.global.enums.AnalysisStatus;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * 수집한 기사 한 건을 저장한다.
 *
 * <p>{@link ArticleStoreService} 와 분리한 이유는 트랜잭션 경계 때문이다. 한 회차를 한 트랜잭션으로 묶으면
 * 기사 한 건이 실패할 때 그 회차 전체가 롤백된다. 같은 클래스 안에서 호출하면 프록시를 거치지 않아
 * {@code @Transactional} 이 걸리지 않으므로 별도 빈으로 둔다.
 */
@Service
@RequiredArgsConstructor
public class ArticleWriter {

	private final NewsOrganizationResolver newsOrganizationResolver;
	private final ArticleRepository articleRepository;

	/**
	 * 기사 한 건을 자체 트랜잭션으로 저장한다. 이미 저장된 기사면 건너뛴다.
	 *
	 * @return 이번에 새로 저장했으면 true, 이미 있던 기사면 false
	 */
	@Transactional
	public boolean write(CollectedArticle article) {
		Long organizationId = newsOrganizationResolver.resolveId(
				article.organizationName(), article.organizationDomain());

		boolean alreadyStored = articleRepository.findIdByUrlHash(article.urlHash()).isPresent();
		articleRepository.insertIfAbsent(
				organizationId,
				article.title(),
				article.url(),
				article.urlHash(),
				article.publishedAt(),
				article.sourceCategory(),
				article.content(),
				article.contentType().name(),
				// 수집 직후에는 아직 분석 전이다. 분석 단계가 이 상태를 보고 대상을 고른다.
				AnalysisStatus.PROCESSING.name());
		return !alreadyStored;
	}
}
