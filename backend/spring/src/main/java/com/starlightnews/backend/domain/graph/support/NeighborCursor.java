package com.starlightnews.backend.domain.graph.support;

import java.nio.charset.StandardCharsets;
import java.util.Base64;

import com.starlightnews.backend.domain.graph.exception.GraphErrorCode;
import com.starlightnews.backend.global.error.BusinessException;

/**
 * 주변 그래프 페이지네이션 커서. 정렬 마지막 항목의 키(neighborScore, nodeType, nodeKey)를 담는다.
 * 정렬 기준은 neighborScore DESC, nodeType ASC, nodeKey ASC 이며, 외부에는 base64(URL-safe, 패딩 없음)
 * 문자열로만 노출되어 Frontend 는 값을 해석하지 않는다.
 */
public record NeighborCursor(double neighborScore, String nodeType, String nodeKey) {

	private static final String DELIMITER = "|";
	private static final int PARTS = 3;

	/** 커서를 base64 문자열로 인코딩한다. */
	public String encode() {
		String raw = neighborScore + DELIMITER + nodeType + DELIMITER + nodeKey;
		return Base64.getUrlEncoder().withoutPadding()
				.encodeToString(raw.getBytes(StandardCharsets.UTF_8));
	}

	/**
	 * base64 문자열을 커서로 디코딩한다. 형식이 올바르지 않으면 {@link GraphErrorCode#INVALID_CURSOR}.
	 */
	public static NeighborCursor decode(String encoded) {
		try {
			String raw = new String(Base64.getUrlDecoder().decode(encoded), StandardCharsets.UTF_8);
			String[] parts = raw.split("\\" + DELIMITER, PARTS);
			if (parts.length != PARTS) {
				throw new BusinessException(GraphErrorCode.INVALID_CURSOR);
			}
			double neighborScore = Double.parseDouble(parts[0]);
			return new NeighborCursor(neighborScore, parts[1], parts[2]);
		} catch (IllegalArgumentException exception) {
			throw new BusinessException(GraphErrorCode.INVALID_CURSOR);
		}
	}
}
