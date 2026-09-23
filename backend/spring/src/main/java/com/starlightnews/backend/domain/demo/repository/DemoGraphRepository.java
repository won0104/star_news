package com.starlightnews.backend.domain.demo.repository;

import java.util.List;

/** 기사 한 건에서 뻗어 나온 서브그래프를 읽는다. */
public interface DemoGraphRepository {

	/**
	 * 기사 노드에서 두 홉까지를 간선 단위로 읽는다.
	 *
	 * <p>1홉은 기사가 직접 건 관계(사건·개체·발언·분류·언론사)이고, 2홉은 그 사건이 건
	 * 관계(행위자·대상·장소·분류·시점·스토리)다. 개체에서 다시 뻗어 나가지는 않는다. 그래프가
	 * 허브 개체를 타고 순식간에 수천 개로 불어나기 때문이다.
	 *
	 * @param articleNodeKey Neo4j Article 의 nodeId
	 * @param primaryOnly    참이면 그 기사가 대표로 다루는 사건만 남긴다. 스치듯 언급된 개체와
	 *                       본문 발언도 함께 빠진다
	 */
	List<DemoGraphRow> findArticleSubgraph(String articleNodeKey, boolean primaryOnly);
}
