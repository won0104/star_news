package com.starlightnews.backend.global.neo4j;

import java.time.LocalDateTime;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.time.ZonedDateTime;
import java.time.format.DateTimeParseException;

import org.neo4j.driver.Value;

/**
 * Neo4j 시각 속성을 읽는다.
 *
 * <p>같은 속성이 노드마다 다른 타입으로 저장돼 있을 수 있다. 시간대가 붙은 값(ZONED DATETIME)이
 * 정상이지만, 시간대 없이 넘어온 요청은 LOCAL DATETIME 으로, 일괄 적재한 데이터는 ISO 문자열로
 * 남아 있었다. 한 노드 때문에 목록 전체가 실패하지 않도록 세 가지를 모두 받는다. 시간대가 없으면
 * 서비스 기준 시간대인 KST 로 본다.
 */
public final class Neo4jDateTimes {

	private static final ZoneOffset KST = ZoneOffset.ofHours(9);

	/**
	 * Cypher 안에서 시각 속성을 ZONED DATETIME 으로 맞추는 식. {@code %s} 에 속성 식을 넣는다.
	 *
	 * <p>정렬·비교 전에 써야 한다. Neo4j 는 타입이 다른 시각 값을 서로 비교하지 못해, 섞여 있으면
	 * 최신순 정렬이 타입별로 갈리고 커서 비교는 null 이 되어 행이 빠진다.
	 */
	public static final String NORMALIZE_CYPHER = """
			CASE
			  WHEN %1$s IS :: LOCAL DATETIME THEN datetime({datetime: %1$s, timezone: '+09:00'})
			  WHEN %1$s IS :: STRING THEN datetime(%1$s)
			  ELSE %1$s
			END""";

	private Neo4jDateTimes() {
	}

	/** 속성 식을 ZONED DATETIME 으로 맞추는 Cypher 식을 만든다. */
	public static String normalize(String propertyExpression) {
		return NORMALIZE_CYPHER.formatted(propertyExpression);
	}

	/**
	 * 시각 값을 읽는다.
	 *
	 * @return 값이 없으면 {@code null}
	 * @throws IllegalStateException 시각으로 읽을 수 없는 타입이거나 형식이 틀린 문자열
	 */
	public static OffsetDateTime toOffsetDateTime(Value value) {
		if (value == null || value.isNull()) {
			return null;
		}

		Object raw = value.asObject();
		if (raw instanceof ZonedDateTime zoned) {
			return zoned.toOffsetDateTime();
		}
		if (raw instanceof OffsetDateTime offset) {
			return offset;
		}
		if (raw instanceof LocalDateTime local) {
			return local.atOffset(KST);
		}
		if (raw instanceof String text) {
			return parse(text);
		}
		throw new IllegalStateException("시각으로 읽을 수 없는 Neo4j 값입니다: " + value.type().name());
	}

	private static OffsetDateTime parse(String text) {
		try {
			return OffsetDateTime.parse(text);
		} catch (DateTimeParseException withoutOffset) {
			try {
				return LocalDateTime.parse(text).atOffset(KST);
			} catch (DateTimeParseException invalid) {
				throw new IllegalStateException("시각 형식이 아닌 Neo4j 문자열입니다: " + text, invalid);
			}
		}
	}
}
