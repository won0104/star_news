package com.starlightnews.backend.global.enums;

/**
 * 기사 본문의 확보 형태. DB에는 상수 이름을 문자열로 저장한다. (articles.content_type)
 * 분석 가능 여부와 요약 입력 데이터 판단에 사용한다.
 */
public enum ContentType {

	/** 기사 전문을 확보한 상태. */
	FULL_TEXT,

	/** 기사 본문의 일부만 확보한 상태. (GNews 무료 플랜 등에서 본문이 잘려 오는 경우) */
	TRUNCATED_TEXT,

	/** 원문 대신 데이터 제공처의 요약만 확보한 상태. */
	SOURCE_SUMMARY
}
