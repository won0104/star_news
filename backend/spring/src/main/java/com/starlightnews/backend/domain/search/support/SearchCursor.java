package com.starlightnews.backend.domain.search.support;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.util.Base64;

import com.starlightnews.backend.domain.search.exception.SearchErrorCode;
import com.starlightnews.backend.global.error.BusinessException;

/**
 * 검색 정렬 위치와 검색어 fingerprint를 담는 불투명 커서.
 * 정렬 정책이 바뀌면 VERSION을 올려 이전 커서를 명확히 거절한다.
 */
public record SearchCursor(
		int matchTier,
		int matchedTokenCount,
		int nodeTypeOrder,
		String nodeKey
) {

	private static final int VERSION = 1;

	public String encode(String queryFingerprint) {
		if (queryFingerprint == null || queryFingerprint.isBlank()) {
			throw invalidRequest();
		}

		try {
			ByteArrayOutputStream bytes = new ByteArrayOutputStream();
			try (DataOutputStream output = new DataOutputStream(bytes)) {
				output.writeInt(VERSION);
				output.writeUTF(queryFingerprint);
				output.writeInt(matchTier);
				output.writeInt(matchedTokenCount);
				output.writeInt(nodeTypeOrder);
				output.writeUTF(nodeKey);
			}
			return Base64.getUrlEncoder().withoutPadding().encodeToString(bytes.toByteArray());
		} catch (IOException exception) {
			throw invalidRequest();
		}
	}

	public static SearchCursor decode(String encoded, String expectedFingerprint) {
		try {
			byte[] bytes = Base64.getUrlDecoder().decode(encoded);
			try (DataInputStream input = new DataInputStream(new ByteArrayInputStream(bytes))) {
				int version = input.readInt();
				String fingerprint = input.readUTF();
				SearchCursor cursor = new SearchCursor(
						input.readInt(), input.readInt(), input.readInt(), input.readUTF());

				if (input.available() != 0
						|| version != VERSION
						|| !fingerprint.equals(expectedFingerprint)
						|| !cursor.isValid()) {
					throw invalidRequest();
				}
				return cursor;
			}
		} catch (IllegalArgumentException | IOException exception) {
			throw invalidRequest();
		}
	}

	private boolean isValid() {
		return matchTier >= 1 && matchTier <= 3
				&& matchedTokenCount >= 1
				&& nodeTypeOrder >= 0 && nodeTypeOrder <= 2
				&& nodeKey != null && !nodeKey.isBlank();
	}

	private static BusinessException invalidRequest() {
		return new BusinessException(SearchErrorCode.INVALID_REQUEST);
	}
}
