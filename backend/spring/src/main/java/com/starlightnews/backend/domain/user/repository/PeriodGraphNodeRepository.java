package com.starlightnews.backend.domain.user.repository;

import java.util.Collection;
import java.util.List;

public interface PeriodGraphNodeRepository {

	/** 기사 여러 건에 직접 연결된 EVENT·ENTITY·STATEMENT를 한 번에 조회한다. */
	List<PeriodGraphNodeRef> findConnectedNodes(Collection<String> articleNodeKeys);
}
