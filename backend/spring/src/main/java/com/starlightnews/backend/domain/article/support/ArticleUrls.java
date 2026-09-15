package com.starlightnews.backend.domain.article.support;

import java.net.URI;
import java.net.URISyntaxException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.Arrays;
import java.util.Locale;
import java.util.stream.Collectors;

/**
 * 기사 URL 정규화와 중복 판별 해시. (articles.url_hash)
 *
 * <p>같은 기사가 추적 파라미터만 다른 주소로 다시 수집되는 것을 막되, 서로 다른 기사를 같은 것으로
 * 합치지는 않도록 정규화 범위를 좁게 잡는다. 경로와 그 외 쿼리 파라미터는 건드리지 않는다.
 */
public final class ArticleUrls {

	/** 기사 내용과 무관한 유입 경로 추적 파라미터. 이것만 제거한다. */
	private static final String[] TRACKING_PARAMS = {"utm_", "fbclid", "gclid", "igshid"};

	private ArticleUrls() {
	}

	/**
	 * 중복 판별을 위해 URL 을 정규화한다.
	 * 스킴·호스트는 소문자로, 프래그먼트(#...)와 추적 파라미터는 제거한다.
	 * 파싱할 수 없는 값이면 앞뒤 공백만 지우고 그대로 돌려준다.
	 */
	public static String normalize(String rawUrl) {
		String trimmed = rawUrl.strip();
		try {
			URI uri = new URI(trimmed);
			if (uri.getScheme() == null || uri.getHost() == null) {
				return trimmed;
			}

			String query = keepMeaningfulQuery(uri.getRawQuery());
			StringBuilder normalized = new StringBuilder()
					.append(uri.getScheme().toLowerCase(Locale.ROOT))
					.append("://")
					.append(uri.getHost().toLowerCase(Locale.ROOT));
			if (uri.getPort() != -1) {
				normalized.append(':').append(uri.getPort());
			}
			normalized.append(uri.getRawPath() == null ? "" : uri.getRawPath());
			if (!query.isEmpty()) {
				normalized.append('?').append(query);
			}
			return normalized.toString();
		} catch (URISyntaxException malformed) {
			return trimmed;
		}
	}

	/** 정규화한 URL 의 SHA-256(32바이트). BINARY(32) 인 articles.url_hash 에 그대로 들어간다. */
	public static byte[] hash(String rawUrl) {
		try {
			return MessageDigest.getInstance("SHA-256")
					.digest(normalize(rawUrl).getBytes(StandardCharsets.UTF_8));
		} catch (NoSuchAlgorithmException unreachable) {
			// SHA-256 은 모든 JVM 이 제공하도록 규정되어 있다.
			throw new IllegalStateException("SHA-256 미지원", unreachable);
		}
	}

	private static String keepMeaningfulQuery(String rawQuery) {
		if (rawQuery == null || rawQuery.isBlank()) {
			return "";
		}
		return Arrays.stream(rawQuery.split("&"))
				.filter(param -> !param.isBlank())
				.filter(param -> !isTracking(param))
				.collect(Collectors.joining("&"));
	}

	private static boolean isTracking(String param) {
		String name = param.split("=", 2)[0].toLowerCase(Locale.ROOT);
		for (String tracking : TRACKING_PARAMS) {
			if (name.startsWith(tracking)) {
				return true;
			}
		}
		return false;
	}
}
