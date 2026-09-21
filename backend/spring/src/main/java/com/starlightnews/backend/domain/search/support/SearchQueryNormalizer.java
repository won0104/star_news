package com.starlightnews.backend.domain.search.support;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.text.Normalizer;
import java.util.ArrayList;
import java.util.HexFormat;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.util.regex.Pattern;

import com.starlightnews.backend.domain.search.exception.SearchErrorCode;
import com.starlightnews.backend.global.error.BusinessException;
import org.springframework.stereotype.Component;

/**
 * 입력 문장을 저장 없이 검색용 Token으로 변환한다.
 * 형태소 분석기 대신 제한된 조사·서술 어미만 제거해 고유명사 훼손을 줄인다.
 */
@Component
public class SearchQueryNormalizer {

	/** 초기 운영 기준. 실제 검색 로그를 확인한 뒤 재조정한다. */
	static final int MAX_TOKEN_COUNT = 20;
	static final int MAX_TOKEN_LENGTH = 50;
	private static final int MIN_STEM_LENGTH = 2;

	private static final Pattern NON_SEARCH_CHARACTER = Pattern.compile("[^\\p{L}\\p{N}]+");
	private static final Pattern WHITESPACE = Pattern.compile("\\s+");

	private static final List<String> PARTICLES = List.of(
			"에게", "에서", "으로", "은", "는", "이", "가", "을", "를", "과", "와", "의", "에", "로", "도", "만");
	private static final List<String> ENDINGS = List.of(
			"하였다", "되었다", "했다", "한다", "된다", "됐다");

	public NormalizedSearchQuery normalize(String rawQuery) {
		String unicodeNormalized = Normalizer.normalize(rawQuery, Normalizer.Form.NFKC)
				.toLowerCase(Locale.ROOT);
		String exactPhrase = collapseWhitespace(unicodeNormalized);
		String tokenSource = collapseWhitespace(NON_SEARCH_CHARACTER.matcher(unicodeNormalized).replaceAll(" "));

		if (tokenSource.isBlank()) {
			throw invalidRequest();
		}

		Set<String> uniqueTokens = new LinkedHashSet<>();
		for (String token : tokenSource.split(" ")) {
			String normalizedToken = normalizeToken(token);
			if (!normalizedToken.isBlank()) {
				validateTokenLength(normalizedToken);
				uniqueTokens.add(normalizedToken);
			}
		}

		if (uniqueTokens.isEmpty() || uniqueTokens.size() > MAX_TOKEN_COUNT) {
			throw invalidRequest();
		}

		List<String> tokens = new ArrayList<>(uniqueTokens);
		String fingerprint = fingerprint(exactPhrase, tokens);
		String fulltextQuery = tokens.stream().map(token -> "*" + token + "*")
				.reduce((left, right) -> left + " OR " + right)
				.orElseThrow(SearchQueryNormalizer::invalidRequest);

		return new NormalizedSearchQuery(exactPhrase, tokens, fingerprint, fulltextQuery);
	}

	private static String normalizeToken(String token) {
		String withoutParticles = stripSuffixes(token, PARTICLES, 2);
		String withoutEnding = stripSuffixes(withoutParticles, ENDINGS, 1);
		return stripSuffixes(withoutEnding, PARTICLES, 1);
	}

	private static String stripSuffixes(String value, List<String> suffixes, int maxRemovals) {
		String result = value;
		for (int removal = 0; removal < maxRemovals; removal++) {
			String stripped = stripOneSuffix(result, suffixes);
			if (stripped.equals(result)) {
				break;
			}
			result = stripped;
		}
		return result;
	}

	private static String stripOneSuffix(String value, List<String> suffixes) {
		for (String suffix : suffixes) {
			if (!value.endsWith(suffix)) {
				continue;
			}
			String stem = value.substring(0, value.length() - suffix.length());
			if (stem.codePointCount(0, stem.length()) >= MIN_STEM_LENGTH) {
				return stem;
			}
		}
		return value;
	}

	private static String collapseWhitespace(String value) {
		return WHITESPACE.matcher(value.strip()).replaceAll(" ");
	}

	private static void validateTokenLength(String token) {
		if (token.codePointCount(0, token.length()) > MAX_TOKEN_LENGTH) {
			throw invalidRequest();
		}
	}

	private static String fingerprint(String exactPhrase, List<String> tokens) {
		String source = exactPhrase + "\u0000" + String.join("\u0000", tokens);
		try {
			byte[] digest = MessageDigest.getInstance("SHA-256")
					.digest(source.getBytes(StandardCharsets.UTF_8));
			return HexFormat.of().formatHex(digest);
		} catch (NoSuchAlgorithmException exception) {
			throw new IllegalStateException("SHA-256 is not available", exception);
		}
	}

	private static BusinessException invalidRequest() {
		return new BusinessException(SearchErrorCode.INVALID_REQUEST);
	}
}
