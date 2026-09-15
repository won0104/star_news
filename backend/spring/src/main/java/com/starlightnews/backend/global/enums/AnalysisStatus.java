package com.starlightnews.backend.global.enums;

/**
 * 기사 분석 및 Neo4j 반영 상태. DB에는 상수 이름을 문자열로 저장한다.
 */
public enum AnalysisStatus {

	PROCESSING,
	COMPLETED,
	FAILED,
	DROPPED
}
