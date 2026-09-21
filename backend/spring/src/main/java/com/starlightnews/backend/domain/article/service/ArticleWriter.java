package com.starlightnews.backend.domain.article.service;

import java.util.List;

import com.starlightnews.backend.domain.article.dto.CollectedArticle;
import com.starlightnews.backend.domain.article.repository.ArticleRepository;
import com.starlightnews.backend.domain.article.support.ArticleContents;
import com.starlightnews.backend.global.enums.AnalysisStatus;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * 수집한 기사 한 건을 저장한다.
 *
 * <p>{@link ArticleStoreService} 와 분리한 이유는 트랜잭션 경계 때문이다. 한 회차를 한 트랜잭션으로 묶으면
 * 기사 한 건이 실패할 때 그 회차 전체가 롤백된다. 같은 클래스 안에서 호출하면 프록시를 거치지 않아
 * {@code @Transactional} 이 걸리지 않으므로 별도 빈으로 둔다.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class ArticleWriter {

	private final NewsOrganizationResolver newsOrganizationResolver;
	private final ArticleRepository articleRepository;

	/**
	 * 기사 한 건을 자체 트랜잭션으로 저장한다. 이미 저장된 기사거나 본문이 기사 본문이 아니면
	 * 건너뛴다.
	 *
	 * @return 이번에 새로 저장했으면 true, 저장하지 않았으면 false
	 */
	@Transactional
	public boolean write(CollectedArticle article) {
		byte[] contentHash = ArticleContents.hash(article.content());
		if (hasStoredUnderOtherTitle(article, contentHash)) {
			return false;
		}

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
				contentHash,
				// 수집 직후에는 아직 분석 전이다. 분석 단계가 이 상태를 보고 대상을 고른다.
				AnalysisStatus.PROCESSING.name());
		return !alreadyStored;
	}

	/**
	 * 같은 본문이 다른 제목으로 이미 저장돼 있는지.
	 *
	 * <p>그렇다면 그 본문은 기사 본문이 아니다. 사이트의 추천 기사 목록이 본문 자리에 들어오면
	 * 제목만 다른 기사가 계속 쌓이고, 분석도 매번 실패한다.
	 *
	 * <p>제목까지 같으면 통신사 기사를 여러 매체가 받아쓴 것이라 그대로 저장한다. 전처리가 한
	 * 회차 안에서 쓰는 기준과 같다. 다른 점은 이미 저장된 기사와도 견준다는 것이다.
	 */
	private boolean hasStoredUnderOtherTitle(CollectedArticle article, byte[] contentHash) {
		List<String> storedTitles = articleRepository.findTitlesByContentHash(contentHash);
		if (storedTitles.isEmpty() || storedTitles.contains(article.title())) {
			return false;
		}

		log.warn("본문이 같은데 제목이 달라 저장하지 않습니다. ({} | 저장된 제목: {})",
				article.title(), storedTitles.get(0));
		return true;
	}
}
