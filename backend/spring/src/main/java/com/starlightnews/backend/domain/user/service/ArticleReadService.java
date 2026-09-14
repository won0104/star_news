package com.starlightnews.backend.domain.user.service;

import java.time.LocalDateTime;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

import com.starlightnews.backend.domain.article.repository.ArticleRepository;
import com.starlightnews.backend.domain.article.repository.ArticleRepository.ArticleGraphRef;
import com.starlightnews.backend.domain.user.domain.ArticleRead;
import com.starlightnews.backend.domain.user.domain.ArticleReadId;
import com.starlightnews.backend.domain.user.domain.UserKnowledgeNode;
import com.starlightnews.backend.domain.user.domain.UserKnowledgeNodeId;
import com.starlightnews.backend.domain.user.repository.ArticleNodeSnapshot;
import com.starlightnews.backend.domain.user.repository.ArticleNodeSnapshotRepository;
import com.starlightnews.backend.domain.user.repository.ArticleReadRepository;
import com.starlightnews.backend.domain.user.repository.UserKnowledgeNodeRepository;
import com.starlightnews.backend.global.error.BusinessException;
import com.starlightnews.backend.global.error.CommonErrorCode;
import lombok.RequiredArgsConstructor;
import org.springframework.dao.DataIntegrityViolationException;
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

	/** 열람 기록을 저장하거나 갱신하고, 연결된 개인 지식 Node 를 Upsert 한다. */
	@Transactional
	public void recordRead(Long userId, Long articleId) {
		ArticleGraphRef graphRef = articleRepository.findGraphRefByArticleId(articleId)
				.orElseThrow(() -> new BusinessException(CommonErrorCode.RESOURCE_NOT_FOUND));

		LocalDateTime now = LocalDateTime.now();
		boolean firstRead = upsertArticleRead(new ArticleReadId(userId, articleId), now);

		if (graphRef.getNodeId() == null) {
			// 아직 AI 분석 전이라 Neo4j 에 대응 Article Node 가 없다. 열람 사실만 남기고 개인 Node 는 건드리지 않는다.
			return;
		}
		applyKnowledgeNodes(userId, graphRef.getNodeId(), firstRead, now);
	}

	/** @return 이 사용자가 해당 기사를 처음 읽은 것이면 true. */
	private boolean upsertArticleRead(ArticleReadId id, LocalDateTime now) {
		if (articleReadRepository.incrementRead(id, now) == 1) {
			return false;
		}

		try {
			articleReadRepository.save(ArticleRead.forFirstRead(id, now));
			return true;
		} catch (DataIntegrityViolationException concurrentInsert) {
			// 동시 첫 열람으로 다른 요청이 먼저 Row 를 만든 경우: 이제 존재하므로 갱신으로 되돌린다.
			// 최초 열람은 먼저 INSERT 한 쪽이 가져가므로 이 요청은 재열람으로 본다.
			articleReadRepository.incrementRead(id, now);
			return false;
		}
	}

	private void applyKnowledgeNodes(Long userId, String articleNodeKey, boolean firstRead, LocalDateTime now) {
		Map<UserKnowledgeNodeId, ArticleNodeSnapshot> byId = new LinkedHashMap<>();
		for (ArticleNodeSnapshot snapshot : findConnectedNodes(articleNodeKey)) {
			byId.putIfAbsent(new UserKnowledgeNodeId(userId, snapshot.nodeType(), snapshot.nodeKey()), snapshot);
		}
		if (byId.isEmpty()) {
			return;
		}

		Set<UserKnowledgeNodeId> existing = Set.copyOf(userKnowledgeNodeRepository.findExistingIds(byId.keySet()));
		if (!existing.isEmpty()) {
			if (firstRead) {
				userKnowledgeNodeRepository.incrementReadForAll(existing, now);
			} else {
				userKnowledgeNodeRepository.touchLastSeenForAll(existing, now);
			}
		}

		byId.forEach((id, snapshot) -> {
			if (existing.contains(id)) {
				return;
			}
			// 이 사용자에게 없던 Node 는 재열람이더라도 이 기사가 그 Node 를 건드린 첫 고유 기사다.
			try {
				userKnowledgeNodeRepository.save(
						UserKnowledgeNode.forFirstRead(id, snapshot.label(), snapshot.topicCode(), now));
			} catch (DataIntegrityViolationException concurrentInsert) {
				// 다른 기사 열람이 같은 Node 를 먼저 만든 경우: 이제 존재하므로 갱신으로 되돌린다.
				userKnowledgeNodeRepository.incrementReadForAll(List.of(id), now);
			}
		});
	}

	private List<ArticleNodeSnapshot> findConnectedNodes(String articleNodeKey) {
		try {
			return articleNodeSnapshotRepository.findConnectedNodes(articleNodeKey);
		} catch (RuntimeException exception) {
			throw new BusinessException(CommonErrorCode.INTERNAL_SERVER_ERROR);
		}
	}
}
