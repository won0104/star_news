package com.starlightnews.backend.domain.user.repository;

import java.time.LocalDateTime;
import java.util.List;

import com.starlightnews.backend.domain.article.domain.Article;
import com.starlightnews.backend.domain.article.domain.NewsOrganization;
import com.starlightnews.backend.domain.user.domain.ArticleRead;
import com.starlightnews.backend.domain.user.domain.ArticleReadId;
import com.starlightnews.backend.domain.user.domain.UserKnowledgeNode;
import com.starlightnews.backend.domain.user.domain.UserKnowledgeNodeId;
import com.starlightnews.backend.domain.user.repository.UserKnowledgeNodeRepository.NewsReportEntityLandscapeRow;
import com.starlightnews.backend.global.enums.NodeType;
import com.starlightnews.backend.support.TestFixtures;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.jdbc.AutoConfigureTestDatabase;
import org.springframework.boot.test.autoconfigure.orm.jpa.DataJpaTest;
import org.springframework.boot.test.autoconfigure.orm.jpa.TestEntityManager;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.util.ReflectionTestUtils;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.groups.Tuple.tuple;

/** 뉴스 리포트 기간 조건과 사용자·Node 유형 격리를 실제 MySQL 쿼리로 검증한다. */
@DataJpaTest
@ActiveProfiles("test")
@AutoConfigureTestDatabase(replace = AutoConfigureTestDatabase.Replace.NONE)
class NewsReportRepositoryTest {

	@Autowired
	private ArticleReadRepository articleReadRepository;

	@Autowired
	private UserKnowledgeNodeRepository userKnowledgeNodeRepository;

	@Autowired
	private TestEntityManager entityManager;

	@BeforeEach
	void insertUsers() {
		TestFixtures.insertUsers(entityManager, 1L, 2L);
	}

	@Test
	void 최근_읽은_기사와_출처는_lastReadAt_기준으로_집계한다() {
		NewsOrganization yonhap = entityManager.persist(new NewsOrganization("연합뉴스"));
		NewsOrganization tech = entityManager.persist(new NewsOrganization("테크뉴스"));
		Article reread = article(yonhap, "재열람 기사", "ECONOMY");
		Article recent = article(yonhap, "최근 기사", "SOCIETY");
		Article old = article(tech, "오래된 기사", "IT_SCIENCE");

		entityManager.persist(read(1L, reread, "2026-01-01T09:00:00", "2026-08-31T09:00:00"));
		entityManager.persist(read(1L, recent, "2026-08-01T09:00:00", "2026-08-01T09:00:00"));
		entityManager.persist(read(1L, old, "2026-05-01T09:00:00", "2026-05-02T09:00:00"));
		entityManager.persist(read(2L, old, "2026-08-01T09:00:00", "2026-08-01T09:00:00"));
		entityManager.flush();
		entityManager.clear();

		LocalDateTime from = LocalDateTime.parse("2026-06-02T00:00:00");
		LocalDateTime to = LocalDateTime.parse("2026-09-03T00:00:00");

		assertThat(articleReadRepository.countRecentReadArticles(1L, from, to)).isEqualTo(2L);
		assertThat(articleReadRepository.countRecentReadArticlesBySource(1L, from, to))
				.extracting(ArticleReadRepository.SourceReadCount::getOrganizationName,
						ArticleReadRepository.SourceReadCount::getCount)
				.containsExactly(tuple("연합뉴스", 2L));
	}

	@Test
	void 주간_분야_행은_firstReadAt_기준이며_Topic이_없는_기사를_제외한다() {
		NewsOrganization organization = entityManager.persist(new NewsOrganization("연합뉴스"));
		Article included = article(organization, "기간 내 최초 열람", "ECONOMY");
		Article reread = article(organization, "기간 전 최초 열람", "SOCIETY");
		Article noTopic = article(organization, "미분류 기사", null);

		entityManager.persist(read(1L, included, "2026-08-17T09:00:00", "2026-08-17T09:00:00"));
		entityManager.persist(read(1L, reread, "2026-05-01T09:00:00", "2026-08-20T09:00:00"));
		entityManager.persist(read(1L, noTopic, "2026-08-18T09:00:00", "2026-08-18T09:00:00"));
		entityManager.flush();
		entityManager.clear();

		List<ArticleReadRepository.FirstReadTopicRow> rows = articleReadRepository.findFirstReadTopics(
				1L, LocalDateTime.parse("2026-06-15T00:00:00"),
				LocalDateTime.parse("2026-09-03T00:00:00"));

		assertThat(rows)
				.extracting(ArticleReadRepository.FirstReadTopicRow::getTopicCode,
						ArticleReadRepository.FirstReadTopicRow::getFirstReadAt)
				.containsExactly(tuple("ECONOMY", LocalDateTime.parse("2026-08-17T09:00:00")));
	}

	@Test
	void 주제_지형은_최근_Entity의_개인과_전체_누적_읽기_수를_반환한다() {
		String hbm = "00000000-0000-0000-0000-000000000001";
		String semiconductor = "00000000-0000-0000-0000-000000000002";
		LocalDateTime old = LocalDateTime.parse("2026-05-01T09:00:00");
		LocalDateTime recent = LocalDateTime.parse("2026-08-31T09:00:00");

		persistReadNode(1L, NodeType.ENTITY, hbm, "HBM", null, old, recent, 3);
		persistReadNode(2L, NodeType.ENTITY, hbm, "HBM", null, old, old, 5);
		persistReadNode(1L, NodeType.ENTITY, semiconductor, "반도체", "IT_SCIENCE",
				old, recent, 3);
		persistReadNode(2L, NodeType.ENTITY, semiconductor, "반도체", "IT_SCIENCE",
				old, old, 2);
		persistReadNode(1L, NodeType.EVENT, "00000000-0000-0000-0000-000000000003",
				"반도체 수출 증가", "IT_SCIENCE", old, recent, 10);
		persistReadNode(1L, NodeType.STATEMENT, "00000000-0000-0000-0000-000000000004",
				"수요가 증가한다", "IT_SCIENCE", old, recent, 10);
		persistReadNode(1L, NodeType.ENTITY, "00000000-0000-0000-0000-000000000005",
				"오래된 Entity", "IT_SCIENCE", old, old, 10);
		persistClickNode(1L, "00000000-0000-0000-0000-000000000006", "클릭만 한 Entity", recent);
		persistReadNode(2L, NodeType.ENTITY, "00000000-0000-0000-0000-000000000007",
				"다른 사용자만 읽은 Entity", "IT_SCIENCE", old, recent, 10);
		entityManager.flush();
		entityManager.clear();

		List<NewsReportEntityLandscapeRow> rows = userKnowledgeNodeRepository.findEntityLandscapeForNewsReport(
				1L,
				LocalDateTime.parse("2026-06-02T00:00:00"),
				LocalDateTime.parse("2026-09-03T00:00:00"), 12);

		assertThat(rows).extracting(
				NewsReportEntityLandscapeRow::getNodeType,
				NewsReportEntityLandscapeRow::getNodeLabel,
				NewsReportEntityLandscapeRow::getTopicCode,
				NewsReportEntityLandscapeRow::getUserReadArticleCount,
				NewsReportEntityLandscapeRow::getGlobalReadArticleCount)
				.containsExactly(
						tuple("ENTITY", "HBM", null, 3L, 8L),
						tuple("ENTITY", "반도체", "IT_SCIENCE", 3L, 5L));
	}

	@Test
	void 주제_지형은_기간_경계를_적용하고_상위_12개만_반환한다() {
		LocalDateTime from = LocalDateTime.parse("2026-06-02T00:00:00");
		LocalDateTime to = LocalDateTime.parse("2026-09-03T00:00:00");
		persistReadNode(1L, NodeType.ENTITY, "10000000-0000-0000-0000-000000000001",
				"시작 경계 Entity", "IT_SCIENCE", from.minusDays(1), from, 99);
		for (int index = 1; index <= 13; index++) {
			String nodeId = String.format("00000000-0000-0000-0000-%012d", index);
			persistReadNode(1L, NodeType.ENTITY, nodeId, "Entity " + index, "IT_SCIENCE",
					from.minusDays(1), from.plusDays(index), index);
		}
		persistReadNode(1L, NodeType.ENTITY, "20000000-0000-0000-0000-000000000001",
				"종료 경계 Entity", "IT_SCIENCE", from, to, 100);
		entityManager.flush();
		entityManager.clear();

		List<NewsReportEntityLandscapeRow> rows = userKnowledgeNodeRepository.findEntityLandscapeForNewsReport(
				1L, from, to, 12);

		assertThat(rows).hasSize(12);
		assertThat(rows).extracting(NewsReportEntityLandscapeRow::getUserReadArticleCount)
				.containsExactly(99L, 13L, 12L, 11L, 10L, 9L, 8L, 7L, 6L, 5L, 4L, 3L);
		assertThat(rows).extracting(NewsReportEntityLandscapeRow::getNodeLabel)
				.contains("시작 경계 Entity")
				.doesNotContain("Entity 1", "Entity 2", "종료 경계 Entity");
	}

	private Article article(NewsOrganization organization, String title, String topicCode) {
		Article article = new Article(title, LocalDateTime.parse("2026-08-01T09:00:00"), organization);
		ReflectionTestUtils.setField(article, "topicCode", topicCode);
		return entityManager.persist(article);
	}

	private ArticleRead read(long userId, Article article, String firstReadAt, String lastReadAt) {
		return new ArticleRead(
				new ArticleReadId(userId, article.getArticleId()),
				LocalDateTime.parse(firstReadAt), LocalDateTime.parse(lastReadAt), 1);
	}

	private void persistReadNode(long userId, NodeType nodeType, String nodeId, String label,
			String topicCode, LocalDateTime firstSeenAt, LocalDateTime lastSeenAt, int readArticleCount) {
		UserKnowledgeNode node = UserKnowledgeNode.forFirstRead(
				new UserKnowledgeNodeId(userId, nodeType, nodeId), label, topicCode, firstSeenAt);
		ReflectionTestUtils.setField(node, "lastSeenAt", lastSeenAt);
		ReflectionTestUtils.setField(node, "readArticleCount", readArticleCount);
		entityManager.persist(node);
	}

	private void persistClickNode(long userId, String nodeId, String label, LocalDateTime lastSeenAt) {
		UserKnowledgeNode node = UserKnowledgeNode.forFirstClick(
				new UserKnowledgeNodeId(userId, NodeType.ENTITY, nodeId), label, null, lastSeenAt);
		entityManager.persist(node);
	}
}
