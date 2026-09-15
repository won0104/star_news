package com.starlightnews.backend.domain.user.service;

import java.time.LocalDateTime;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import com.starlightnews.backend.domain.article.repository.ArticleRepository;
import com.starlightnews.backend.domain.article.repository.ArticleRepository.ArticleGraphRef;
import com.starlightnews.backend.domain.user.domain.UserKnowledgeNodeId;
import com.starlightnews.backend.domain.user.repository.ArticleNodeSnapshot;
import com.starlightnews.backend.domain.user.repository.ArticleNodeSnapshotRepository;
import com.starlightnews.backend.domain.user.repository.ArticleReadRepository;
import com.starlightnews.backend.domain.user.repository.UserKnowledgeNodeRepository;
import com.starlightnews.backend.global.error.BusinessException;
import com.starlightnews.backend.global.error.CommonErrorCode;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * 기사 상세 화면 진입 1회를 article_reads 에 기록하고, 그 기사에 연결된 개인 지식 Node 를 반영한다.
 * 갱신을 먼저 시도하고(재열람이 hot path 라 UPDATE 한 번), 대상 Row 가 없을 때만 새 Row 를 만든다.
 *
 * <p>개인 그래프 요약의 참여도 캐시(ExploredNodeCountCache)는 건드리지 않는다. 그 집계는
 * node_click_count > 0 인 Node 만 세는데, 열람으로 생긴 Row 는 click_count 가 0 이고
 * 이미 클릭된 Row 에 열람이 더해져도 개수는 그대로라 캐시 값이 바뀌지 않는다.
 */
@Service
@RequiredArgsConstructor
public class ArticleReadService {

	private final ArticleReadRepository articleReadRepository;
	private final ArticleRepository articleRepository;
	private final ArticleNodeSnapshotRepository articleNodeSnapshotRepository;
	private final UserKnowledgeNodeRepository userKnowledgeNodeRepository;

	/** MySQL upsert 의 영향 행 수. INSERT 되면 1, 기존 행이 갱신되면 2. */
	private static final int INSERTED = 1;

	/** 열람 기록을 저장하거나 갱신하고, 연결된 개인 지식 Node 를 Upsert 한다. */
	@Transactional
	public void recordRead(Long userId, Long articleId) {
		ArticleGraphRef graphRef = articleRepository.findGraphRefByArticleId(articleId)
				.orElseThrow(() -> new BusinessException(CommonErrorCode.RESOURCE_NOT_FOUND));

		LocalDateTime now = LocalDateTime.now();
		boolean firstRead = articleReadRepository.upsertRead(userId, articleId, now) == INSERTED;

		if (graphRef.getNodeId() == null) {
			// 아직 AI 분석 전이라 Neo4j 에 대응 Article Node 가 없다. 열람 사실만 남기고 개인 Node 는 건드리지 않는다.
			return;
		}
		applyKnowledgeNodes(userId, graphRef.getNodeId(), firstRead, now);
	}

	private void applyKnowledgeNodes(Long userId, String articleNodeKey, boolean firstRead, LocalDateTime now) {
		Map<UserKnowledgeNodeId, ArticleNodeSnapshot> byId = new LinkedHashMap<>();
		for (ArticleNodeSnapshot snapshot : findConnectedNodes(articleNodeKey)) {
			byId.putIfAbsent(new UserKnowledgeNodeId(userId, snapshot.nodeType(), snapshot.nodeKey()), snapshot);
		}

		// 이 기사를 처음 읽을 때만 기존 Node 의 고유 기사 수를 늘린다. 없던 Node 는 INSERT 쪽에서 1 로 시작한다.
		int readIncrement = firstRead ? 1 : 0;
		byId.forEach((id, snapshot) -> userKnowledgeNodeRepository.upsertRead(
				userId, id.getNodeType().name(), id.getNodeId(),
				snapshot.label(), snapshot.topicCode(), readIncrement, now));
	}

	private List<ArticleNodeSnapshot> findConnectedNodes(String articleNodeKey) {
		try {
			return articleNodeSnapshotRepository.findConnectedNodes(articleNodeKey);
		} catch (RuntimeException exception) {
			throw new BusinessException(CommonErrorCode.INTERNAL_SERVER_ERROR);
		}
	}
}
