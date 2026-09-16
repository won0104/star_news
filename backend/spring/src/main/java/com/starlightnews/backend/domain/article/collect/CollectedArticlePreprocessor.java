package com.starlightnews.backend.domain.article.collect;

import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.util.regex.Pattern;

import com.starlightnews.backend.domain.article.dto.CollectedArticle;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

/**
 * 수집한 기사를 저장 전에 다듬는다.

 * <p>여기서 버린 기사는 저장되지 않는다. 버린 건 전부 로그에 기록한다.
 */
@Slf4j
@Component
public class CollectedArticlePreprocessor {

	/**
	 * 분석에 쓸 수 있는 최소 본문 길이.
	 */
	private static final int MIN_CONTENT_LENGTH = 200;

	/**
	 * 사건이 아니라 명단·정보라 분석 대상이 아닌 기사의 제목 접두 태그.
	 */
	private static final List<String> EXCLUDED_TITLE_PREFIXES =
			List.of("[인사]", "[부고]", "[동정]", "[신간]");

	/** 제목 어디에 있든 분석 대상이 아닌 문구. 넓게 잡으면 정상 기사가 걸리므로 구체적으로 둔다. */
	private static final List<String> EXCLUDED_TITLE_KEYWORDS =
			List.of("오늘의 운세", "띠별 운세");

	/** 본문에서 꺼낸 줄을 제목으로 볼 수 있는 최대 길이. 실측한 정상 제목의 99%가 64자 이하다. */
	private static final int MAX_TITLE_LENGTH = 70;

	/** 통신사 기사의 바이라인. */
	private static final Pattern BYLINE = Pattern.compile("(기자|특파원|통신원)\\s*=");

	/**
	 * <p>{@code ?} 나 {@code …} 로 끝나는 제목은 흔하므로 평서문 종결만 본다.
	 */
	private static final Pattern SENTENCE_END = Pattern.compile("[다요]\\.$");

	/** 본문 앞머리에 붙는 사이트 UI·분류 문구. 제목을 찾을 때 건너뛴다. */
	private static final Set<String> LEADING_NOISE = Set.of(
			"AD", "기사 본문 영역", "AI 해설 기사", "크게보기", "기사 읽어주기", "세 줄 요약",
			"정치", "경제", "사회", "세계", "문화", "스포츠", "국제", "IT", "연예", "공유하기");

	/**
	 * 저장할 기사만 남기고, 고칠 수 있는 것은 고친다.
	 *
	 * @return 분석에 쓸 수 있는 기사 목록
	 */
	public List<CollectedArticle> process(List<CollectedArticle> articles) {
		if (articles.isEmpty()) {
			return List.of();
		}

		List<CollectedArticle> kept = articles.stream()
				.filter(this::isAnalyzable)
				.map(this::repairTitle)
				.toList();

		int dropped = articles.size() - kept.size();
		if (dropped > 0) {
			log.info("전처리: {}건 중 {}건을 제외했습니다.", articles.size(), dropped);
		}
		return kept;
	}

	/**
	 * 제목이 언론사명으로만 온 기사의 제목을 본문에서 찾아 채운다.
	 * <p>찾지 못하면 원본을 그대로 둔다.
	 */
	private CollectedArticle repairTitle(CollectedArticle article) {
		if (!hasOutletNameAsTitle(article)) {
			return article;
		}

		String candidate = firstMeaningfulLine(article.content());
		if (!looksLikeTitle(candidate)) {
			log.info("제목을 본문에서 찾지 못해 원본을 유지합니다. ({}, {})",
					article.organizationName(), article.url());
			return article;
		}

		log.info("제목을 본문에서 보정했습니다. ({} -> {})", article.title(), candidate);
		return new CollectedArticle(candidate, article.url(), article.urlHash(),
				article.publishedAt(), article.content(), article.contentType(),
				article.sourceCategory(), article.organizationName(), article.organizationDomain());
	}

	/**
	 * 제목이 언론사명과 같은지. 공백을 무시하고 본다.
	 */
	private boolean hasOutletNameAsTitle(CollectedArticle article) {
		if (article.title() == null || article.organizationName() == null) {
			return false;
		}
		return withoutWhitespace(article.title()).equals(withoutWhitespace(article.organizationName()));
	}

	private String withoutWhitespace(String value) {
		return value.replaceAll("\\s+", "");
	}

	/** 사이트 UI 문구를 건너뛴 첫 줄. 없으면 빈 문자열 */
	private String firstMeaningfulLine(String content) {
		if (content == null) {
			return "";
		}
		return content.lines()
				.map(String::strip)
				.filter(line -> !line.isEmpty() && !LEADING_NOISE.contains(line))
				.findFirst()
				.orElse("");
	}

	/** 제목으로 쓸 수 있는 줄인지. 길이·바이라인·문장 종결 셋을 모두 본다. */
	private boolean looksLikeTitle(String line) {
		return !line.isEmpty()
				&& line.length() <= MAX_TITLE_LENGTH
				&& !BYLINE.matcher(line).find()
				&& !SENTENCE_END.matcher(line).find();
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
