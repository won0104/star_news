package com.starlightnews.backend.domain.article.support;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;

/**
 * 기사 본문 해시.
 *
 * <p>같은 본문이 다시 들어왔는지 보려고 쓴다. 본문은 MEDIUMTEXT 라 그대로 견주면 인덱스를 쓸 수
 * 없다. 32바이트 해시를 컬럼으로 두고 찾는다.
 */
public final class ArticleContents {

	private ArticleContents() {
	}

	/** 본문의 SHA-256(32바이트). BINARY(32) 인 articles.content_hash 에 그대로 들어간다. */
	public static byte[] hash(String content) {
		try {
			return MessageDigest.getInstance("SHA-256")
					.digest(String.valueOf(content).getBytes(StandardCharsets.UTF_8));
		} catch (NoSuchAlgorithmException unreachable) {
			// SHA-256 은 모든 JVM 이 제공하도록 규정되어 있다.
			throw new IllegalStateException("SHA-256 미지원", unreachable);
		}
	}
}
