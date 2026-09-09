package com.starlightnews.backend.global.security;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;

/**
 * 토큰을 저장소에 넣기 전 단방향 해시한다. (원문 대신 해시를 저장해 유출 피해를 줄인다)
 * 토큰 자체가 고엔트로피 문자열이므로 비밀번호용 BCrypt 대신 SHA-256 으로 충분하다.
 */
public final class TokenHasher {

	private TokenHasher() {
	}

	public static String sha256Hex(String value) {
		try {
			byte[] digest = MessageDigest.getInstance("SHA-256")
					.digest(value.getBytes(StandardCharsets.UTF_8));
			return HexFormat.of().formatHex(digest);
		} catch (NoSuchAlgorithmException exception) {
			throw new IllegalStateException("SHA-256 미지원", exception);
		}
	}
}
