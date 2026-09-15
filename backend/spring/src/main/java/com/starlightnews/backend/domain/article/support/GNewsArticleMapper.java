package com.starlightnews.backend.domain.article.support;

import java.net.URI;
import java.net.URISyntaxException;
import java.time.Instant;
import java.time.LocalDateTime;
import java.time.ZoneId;
import java.time.format.DateTimeParseException;
import java.util.Optional;
import java.util.regex.Pattern;

import com.starlightnews.backend.domain.article.dto.CollectedArticle;
import com.starlightnews.backend.domain.article.dto.GNewsArticlesResponse.GNewsArticle;
import com.starlightnews.backend.global.enums.ContentType;

/**
 * GNews 기사 응답을 저장 직전 형태({@link CollectedArticle})로 옮긴다.
 *
 * <p>저장할 수 없는 기사(필수 값 누락, 시각 파싱 불가)는 예외 대신 빈 Optional 로 걸러낸다.
 * 수집은 한 번에 수십 건을 다루므로 한 건이 이상하다고 수집 전체를 중단시키지 않는다.
 */
public final class GNewsArticleMapper {

	/** DB DATETIME(6) 은 KST 벽시계로 저장한다. */
	private static final ZoneId KST = ZoneId.of("Asia/Seoul");

	/** GNews 가 본문을 자를 때 끝에 붙이는 표시. 예: "... [1234 chars]" */
	private static final Pattern TRUNCATION_MARKER = Pattern.compile("\\[\\d+\\s+chars]\\s*$");

	/** articles.title 이 VARCHAR(500) 이라 그 이상은 저장할 수 없다. */
	private static final int MAX_TITLE_LENGTH = 500;

	private GNewsArticleMapper() {
	}

	/**
	 * @param sourceCategory 이 기사를 받아온 GNews 카테고리. 변환 없이 그대로 보존한다.
	 * @return 저장 가능한 기사면 값이 있고, 필수 값이 없으면 빈 Optional
	 */
	public static Optional<CollectedArticle> toCollected(GNewsArticle article, String sourceCategory) {
		if (isBlank(article.title()) || isBlank(article.url()) || article.source() == null
				|| isBlank(article.source().name())) {
			return Optional.empty();
		}

		LocalDateTime publishedAt = parsePublishedAt(article.publishedAt());
		if (publishedAt == null) {
			return Optional.empty();
		}

		// content 는 요금제·기사에 따라 비어 올 수 있다. 그때는 제공처 요약이라도 본문으로 쓴다.
		// articles.content 가 NOT NULL 이라 둘 다 없으면 저장할 수 없다.
		String body = firstNonBlank(article.content(), article.description());
		if (body == null) {
			return Optional.empty();
		}

		return Optional.of(new CollectedArticle(
				truncateTitle(article.title().strip()),
				article.url().strip(),
				ArticleUrls.hash(article.url()),
				publishedAt,
				body.strip(),
				resolveContentType(article.content(), body),
				sourceCategory,
				article.source().name().strip(),
				domainOf(article.source().url())));
	}

	/** GNews 는 ISO-8601 UTC(예: 2026-09-14T05:00:00Z)로 준다. 파싱 불가면 null. */
	private static LocalDateTime parsePublishedAt(String publishedAt) {
		if (isBlank(publishedAt)) {
			return null;
		}
		try {
			return LocalDateTime.ofInstant(Instant.parse(publishedAt.strip()), KST);
		} catch (DateTimeParseException unparsable) {
			return null;
		}
	}

	/**
	 * content 가 비어 description 으로 대체했으면 제공처 요약,
	 * content 끝에 잘림 표시가 있으면 일부 본문, 그 외에는 전문으로 본다.
	 */
	private static ContentType resolveContentType(String rawContent, String body) {
		if (isBlank(rawContent)) {
			return ContentType.SOURCE_SUMMARY;
		}
		return TRUNCATION_MARKER.matcher(body).find()
				? ContentType.TRUNCATED_TEXT
				: ContentType.FULL_TEXT;
	}

	/** 언론사 홈 URL 에서 호스트만 뽑는다. news_organizations.domain 용이며 없으면 null. */
	private static String domainOf(String sourceUrl) {
		if (isBlank(sourceUrl)) {
			return null;
		}
		try {
			String host = new URI(sourceUrl.strip()).getHost();
			return host == null ? null : host.toLowerCase(java.util.Locale.ROOT);
		} catch (URISyntaxException malformed) {
			return null;
		}
	}

	private static String truncateTitle(String title) {
		return title.length() <= MAX_TITLE_LENGTH ? title : title.substring(0, MAX_TITLE_LENGTH);
	}

	private static String firstNonBlank(String first, String second) {
		if (!isBlank(first)) {
			return first;
		}
		return isBlank(second) ? null : second;
	}

	private static boolean isBlank(String value) {
		return value == null || value.isBlank();
	}
}
