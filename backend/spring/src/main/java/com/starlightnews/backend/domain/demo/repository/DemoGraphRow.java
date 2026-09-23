package com.starlightnews.backend.domain.demo.repository;

/**
 * 기사 서브그래프 조회의 한 줄. 간선 하나와 그 양쪽 노드를 담는다.
 *
 * <p>같은 노드가 여러 줄에 반복해서 나온다. 노드 목록으로 접는 일은 서비스가 한다.
 */
public record DemoGraphRow(
		String fromKey,
		String fromType,
		String fromLabel,
		String fromSubType,
		String relation,
		boolean primary,
		String toKey,
		String toType,
		String toLabel,
		String toSubType
) {
}
