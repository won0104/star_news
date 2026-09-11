package com.starlightnews.backend.domain.user.support;

import java.nio.charset.StandardCharsets;
import java.time.OffsetDateTime;
import java.time.format.DateTimeParseException;
import java.util.Base64;

import com.starlightnews.backend.domain.graph.exception.GraphErrorCode;
import com.starlightnews.backend.global.error.BusinessException;

/**
 * 개인 그래프 노드별 읽은 기사 목록 페이지네이션 커서. 정렬 마지막 항목의 키(lastReadAt, articleId)를 담는다.
 * `-28`의 ArticleCursor 와 구조는 같지만, 정렬 기준이 기사 발행일이 아니라 "내가 읽은 시각"이라 의미가 달라
 * 별도 타입으로 둔다. 외부에는 base64(URL-safe, 패딩 없음) 문자열로만 노출된다.
 */
public record ArticleReadCursor(OffsetDateTime lastReadAt, long articleId) {

	private static final String DELIMITER = "|";

	/** 커서를 base64 문자열로 인코딩한다. */
	public String encode() {
		String raw = lastReadAt.toString() + DELIMITER + articleId;
		return Base64.getUrlEncoder().withoutPadding()
				.encodeToString(raw.getBytes(StandardCharsets.UTF_8));
	}

	/**
	 * base64 문자열을 커서로 디코딩한다. 형식이 올바르지 않으면 {@link GraphErrorCode#INVALID_CURSOR}.
	 */
	public static ArticleReadCursor decode(String encoded) {
		try {
			String raw = new String(Base64.getUrlDecoder().decode(encoded), StandardCharsets.UTF_8);
			int split = raw.indexOf(DELIMITER);
			if (split < 0) {
				throw new BusinessException(GraphErrorCode.INVALID_CURSOR);
			}
			OffsetDateTime lastReadAt = OffsetDateTime.parse(raw.substring(0, split));
			long articleId = Long.parseLong(raw.substring(split + DELIMITER.length()));
			return new ArticleReadCursor(lastReadAt, articleId);
		} catch (IllegalArgumentException | DateTimeParseException exception) {
			throw new BusinessException(GraphErrorCode.INVALID_CURSOR);
		}
	}
}
