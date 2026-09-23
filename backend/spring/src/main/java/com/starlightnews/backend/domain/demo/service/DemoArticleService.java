package com.starlightnews.backend.domain.demo.service;

import java.time.LocalDateTime;
import java.time.ZoneId;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

import com.starlightnews.backend.domain.article.analysis.ArticleAnalysisOutcome;
import com.starlightnews.backend.domain.article.analysis.ArticleAnalysisRecorder;
import com.starlightnews.backend.domain.article.analysis.ArticleAnalyzeClient;
import com.starlightnews.backend.domain.article.analysis.dto.ArticleAnalyzeRequest;
import com.starlightnews.backend.domain.article.dto.CollectedArticle;
import com.starlightnews.backend.domain.article.repository.ArticleRepository;
import com.starlightnews.backend.domain.article.service.ArticleWriter;
import com.starlightnews.backend.domain.article.support.ArticleUrls;
import com.starlightnews.backend.domain.demo.dto.DemoArticleRequest;
import com.starlightnews.backend.domain.demo.dto.DemoGraphResponse;
import com.starlightnews.backend.domain.demo.exception.DemoErrorCode;
import com.starlightnews.backend.domain.demo.repository.DemoGraphRepository;
import com.starlightnews.backend.domain.demo.repository.DemoGraphRow;
import com.starlightnews.backend.global.enums.ContentType;
import com.starlightnews.backend.global.error.BusinessException;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

/**
 * 시연용으로 넣은 기사 한 건을 저장하고 그 자리에서 분석한다.
 *
 * <p>수집·분석 배치가 하는 일을 기사 한 건에 대해 동기로 수행한다. 저장과 분석 반영은 기존
 * {@link ArticleWriter}·{@link ArticleAnalysisRecorder} 를 그대로 쓴다. 배치와 다른 점은 회차·재시도·
 * 시간 예산이 없다는 것뿐이고, 결과로 만들어지는 그래프는 평소 기사와 완전히 같다.
 *
 * <p>분석은 FastAPI 가 AI 워커를 기다리므로 30~60초, 길면 150초까지 걸린다. 호출한 쪽이 그동안
 * 기다린다.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class DemoArticleService {

	/** 시연 기사임을 남기는 표시. articles.source_category 에 들어간다. */
	public static final String DEMO_CATEGORY = "DEMO";

	/** 언론사를 적지 않았을 때 쓰는 이름. */
	private static final String DEFAULT_SOURCE_NAME = "시연";

	/**
	 * 시연 기사에 붙이는 URL.
	 *
	 * <p>articles.url 은 NOT NULL 이고 url_hash 가 유니크라 실제 주소가 없어도 무언가는 있어야 한다.
	 * 같은 본문을 여러 번 시연할 수 있어야 하므로 호출마다 새 UUID 를 붙인다.
	 */
	private static final String DEMO_URL_PREFIX = "https://demo.starlightnews.local/articles/";

	private static final ZoneId SEOUL = ZoneId.of("Asia/Seoul");

	private final ArticleWriter articleWriter;
	private final ArticleRepository articleRepository;
	private final ArticleAnalyzeClient analyzeClient;
	private final ArticleAnalysisRecorder analysisRecorder;
	private final DemoGraphRepository demoGraphRepository;

	/**
	 * 기사를 저장하고 분석한 뒤 그 기사에서 만들어진 그래프를 돌려준다.
	 *
	 * @throws BusinessException 저장에 실패했거나(같은 본문이 다른 제목으로 이미 있음) 분석이
	 *                           실패했을 때
	 */
	public DemoGraphResponse createAndAnalyze(DemoArticleRequest request, boolean primaryOnly) {
		long articleId = store(request);
		analyze(articleId, request);
		return findGraph(articleId, primaryOnly);
	}

	/** 이미 분석이 끝난 기사의 그래프를 다시 읽는다. */
	public DemoGraphResponse findGraph(long articleId, boolean primaryOnly) {
		ArticleRepository.DemoArticle article = articleRepository.findDemoArticle(articleId)
				.orElseThrow(() -> new BusinessException(DemoErrorCode.DEMO_ARTICLE_NOT_FOUND));

		if (article.getNodeId() == null) {
			throw new BusinessException(DemoErrorCode.DEMO_ARTICLE_NOT_ANALYZED);
		}

		List<DemoGraphRow> rows = demoGraphRepository.findArticleSubgraph(
				article.getNodeId(), primaryOnly);
		return toResponse(articleId, article, rows);
	}

	/** 기사를 저장하고 그 ID 를 돌려준다. */
	private long store(DemoArticleRequest request) {
		String url = DEMO_URL_PREFIX + UUID.randomUUID();
		byte[] urlHash = ArticleUrls.hash(url);
		LocalDateTime publishedAt = request.publishedAt() != null
				? request.publishedAt()
				: LocalDateTime.now(SEOUL);
		String sourceName = request.sourceName() == null || request.sourceName().isBlank()
				? DEFAULT_SOURCE_NAME
				: request.sourceName().strip();

		boolean stored = articleWriter.write(new CollectedArticle(
				request.title().strip(),
				url,
				urlHash,
				publishedAt,
				request.content().strip(),
				ContentType.FULL_TEXT,
				DEMO_CATEGORY,
				sourceName,
				null));

		// 같은 본문이 다른 제목으로 이미 있으면 저장을 건너뛴다. 시연에서는 그 이유를 알려 줘야 한다.
		if (!stored) {
			throw new BusinessException(DemoErrorCode.DEMO_ARTICLE_NOT_STORED);
		}

		return articleRepository.findIdByUrlHash(urlHash)
				.orElseThrow(() -> new BusinessException(DemoErrorCode.DEMO_ARTICLE_NOT_STORED));
	}

	/** FastAPI 에 분석을 맡기고 결과를 기사에 반영한다. */
	private void analyze(long articleId, DemoArticleRequest request) {
		ArticleRepository.DemoArticle stored = articleRepository.findDemoArticle(articleId)
				.orElseThrow(() -> new BusinessException(DemoErrorCode.DEMO_ARTICLE_NOT_FOUND));

		ArticleAnalysisOutcome outcome = analyzeClient.analyze(ArticleAnalyzeRequest.of(
				articleId,
				request.title().strip(),
				request.content().strip(),
				stored.getOrganizationId(),
				stored.getOrganizationName(),
				stored.getPublishedAt()));

		ArticleAnalysisRecorder.Recorded recorded = analysisRecorder.record(articleId, outcome);
		if (recorded != ArticleAnalysisRecorder.Recorded.COMPLETED) {
			log.warn("시연 기사 분석이 완료되지 않았습니다. (articleId={}, 결과={})", articleId, recorded);
			throw new BusinessException(DemoErrorCode.DEMO_ANALYSIS_FAILED);
		}
	}

	/**
	 * 간선 목록을 노드 목록과 간선 목록으로 나눈다.
	 *
	 * <p>같은 노드가 여러 간선에 반복해 나오므로 키로 접는다. 화면이 그리는 순서가 매번 달라지지
	 * 않도록 나온 순서를 유지한다.
	 */
	private DemoGraphResponse toResponse(long articleId,
			ArticleRepository.DemoArticle article, List<DemoGraphRow> rows) {
		Map<String, DemoGraphResponse.Node> nodes = new LinkedHashMap<>();
		List<DemoGraphResponse.Edge> edges = new ArrayList<>(rows.size());

		for (DemoGraphRow row : rows) {
			putNode(nodes, row.fromKey(), row.fromType(), row.fromLabel(), row.fromSubType());
			putNode(nodes, row.toKey(), row.toType(), row.toLabel(), row.toSubType());
			edges.add(new DemoGraphResponse.Edge(
					row.fromKey(), row.toKey(), row.relation(), row.primary()));
		}

		return new DemoGraphResponse(
				articleId,
				article.getNodeId(),
				article.getTopicCode(),
				article.getSubtopicCode(),
				List.copyOf(nodes.values()),
				List.copyOf(edges));
	}

	private void putNode(Map<String, DemoGraphResponse.Node> nodes, String key, String type,
			String label, String subType) {
		if (key == null) {
			return;
		}
		nodes.computeIfAbsent(key, nodeKey -> new DemoGraphResponse.Node(
				nodeKey,
				type == null ? null : type.toUpperCase(java.util.Locale.ROOT),
				label,
				subType));
	}
}
