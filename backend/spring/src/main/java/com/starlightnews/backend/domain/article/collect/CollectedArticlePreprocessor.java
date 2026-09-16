package com.starlightnews.backend.domain.article.collect;

import java.util.List;
import java.util.Locale;

import com.starlightnews.backend.domain.article.dto.CollectedArticle;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

/**
 * 수집한 기사를 저장 전에 다듬는다.
 *
 * <p>제공처가 준 그대로는 분석에 쓰기 어려운 것들이 섞여 있다. 분석할 내용이 없는 기사, 제목이
 * 언론사명으로만 온 기사, 본문에 사이트 UI 문구가 붙은 기사 같은 것들이다.
 *
 * <p>여기서 버린 기사는 저장되지 않는다. 되돌릴 수 없으므로 규칙은 좁게 잡고, 버린 건 전부
 * 로그에 남겨 나중에 오탐을 확인할 수 있게 한다.
 */
@Slf4j
@Component
public class CollectedArticlePreprocessor {

	/**
	 * 분석에 쓸 수 있는 최소 본문 길이.
	 *
	 * <p>실측한 정상 기사의 최소가 500자 안팎이라 여유를 두고 잡았다. 이 아래는 본문이 아예 비었거나
	 * 속보 한 줄이라 Event 를 만들 수 없다.
	 */
	private static final int MIN_CONTENT_LENGTH = 200;

	/**
	 * 사건이 아니라 명단·정보라 분석 대상이 아닌 기사의 제목 접두 태그.
	 *
	 * <p>부분 일치가 아니라 접두사로만 본다. "인사"가 제목 가운데 들어간 기사까지 버리면 안 된다.
	 */
	private static final List<String> EXCLUDED_TITLE_PREFIXES =
			List.of("[인사]", "[부고]", "[동정]", "[신간]");

	/** 제목 어디에 있든 분석 대상이 아닌 문구. 넓게 잡으면 정상 기사가 걸리므로 구체적으로 둔다. */
	private static final List<String> EXCLUDED_TITLE_KEYWORDS =
			List.of("오늘의 운세", "띠별 운세");

	/**
	 * 저장할 기사만 남긴다.
	 *
	 * @return 분석에 쓸 수 있는 기사 목록
	 */
	public List<CollectedArticle> process(List<CollectedArticle> articles) {
		if (articles.isEmpty()) {
			return List.of();
		}

		List<CollectedArticle> kept = articles.stream().filter(this::isAnalyzable).toList();

		int dropped = articles.size() - kept.size();
		if (dropped > 0) {
			log.info("전처리: {}건 중 {}건을 제외했습니다.", articles.size(), dropped);
		}
		return kept;
	}

	private boolean isAnalyzable(CollectedArticle article) {
		if (hasTooLittleContent(article)) {
			log.info("본문이 짧아 제외합니다. ({}자, {})", contentLength(article), article.title());
			return false;
		}
		if (isNotNews(article.title())) {
			log.info("분석 대상이 아니라 제외합니다. ({})", article.title());
			return false;
		}
		return true;
	}

	private boolean hasTooLittleContent(CollectedArticle article) {
		return contentLength(article) < MIN_CONTENT_LENGTH;
	}

	private int contentLength(CollectedArticle article) {
		return article.content() == null ? 0 : article.content().strip().length();
	}

	/** 사건을 다루지 않는 기사인지. 인사·부고·운세처럼 명단이나 정보만 있는 것들이다. */
	private boolean isNotNews(String title) {
		if (title == null) {
			return false;
		}

		String normalized = title.strip().toLowerCase(Locale.KOREAN);
		return EXCLUDED_TITLE_PREFIXES.stream().anyMatch(normalized::startsWith)
				|| EXCLUDED_TITLE_KEYWORDS.stream().anyMatch(normalized::contains);
	}
}
