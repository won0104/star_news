package com.starlightnews.backend.domain.article.repository;

import java.time.LocalDateTime;
import java.util.List;

import com.starlightnews.backend.domain.article.domain.Article;
import com.starlightnews.backend.domain.article.domain.NewsOrganization;
import com.starlightnews.backend.domain.article.support.ArticleUrls;
import com.starlightnews.backend.global.enums.AnalysisStatus;
import com.starlightnews.backend.global.enums.ContentType;
import com.starlightnews.backend.global.enums.SummaryStatus;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.jdbc.AutoConfigureTestDatabase;
import org.springframework.boot.test.autoconfigure.orm.jpa.DataJpaTest;
import org.springframework.boot.test.autoconfigure.orm.jpa.TestEntityManager;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.util.ReflectionTestUtils;

import static org.assertj.core.api.Assertions.assertThat;

@DataJpaTest
@ActiveProfiles("test")
@AutoConfigureTestDatabase(replace = AutoConfigureTestDatabase.Replace.NONE)
class ArticleRepositoryTest {

	@Autowired
	private ArticleRepository articleRepository;

	@Autowired
	private TestEntityManager entityManager;

	@Test
	void articleId로_기사_상세와_언론사를_함께_조회한다() {
		NewsOrganization organization = entityManager.persist(new NewsOrganization("연합뉴스"));
		Article article = entityManager.persist(new Article(
				"기사 제목",
				LocalDateTime.of(2026, 8, 31, 10, 0),
				organization,
				"저장된 요약",
				AnalysisStatus.COMPLETED));
		entityManager.flush();
		entityManager.clear();

		Article found = articleRepository.findDetailByArticleId(
				article.getArticleId(), AnalysisStatus.COMPLETED).orElseThrow();

		assertThat(found.getTitle()).isEqualTo("기사 제목");
		assertThat(found.getOrganization().getName()).isEqualTo("연합뉴스");
		assertThat(found.getSummary()).isEqualTo("저장된 요약");
		assertThat(found.getSummaryStatus()).isEqualTo(SummaryStatus.COMPLETED);
	}

	@Test
	void 상세_조회시_없는_articleId면_빈_Optional이다() {
		assertThat(articleRepository.findDetailByArticleId(999L, AnalysisStatus.COMPLETED)).isEmpty();
	}

	@Test
	void 분석이_완료되지_않은_기사는_상세_조회에서_제외한다() {
		NewsOrganization organization = entityManager.persist(new NewsOrganization("연합뉴스"));
		Article article = entityManager.persist(new Article(
				"분석 중인 기사",
				LocalDateTime.of(2026, 8, 31, 10, 0),
				organization,
				null,
				AnalysisStatus.PROCESSING));
		entityManager.flush();
		entityManager.clear();

		assertThat(articleRepository.findDetailByArticleId(
				article.getArticleId(), AnalysisStatus.COMPLETED)).isEmpty();
	}

	@Test
	void 요약_생성_상태는_한_요청만_PROCESSING으로_선점한다() {
		NewsOrganization organization = entityManager.persist(new NewsOrganization("연합뉴스"));
		Article article = entityManager.persist(new Article(
				"요약 대상 기사",
				LocalDateTime.of(2026, 9, 17, 9, 0),
				organization,
				null,
				AnalysisStatus.COMPLETED));
		entityManager.flush();

		int first = claimSummary(article.getArticleId());
		int second = claimSummary(article.getArticleId());
		entityManager.clear();

		assertThat(first).isEqualTo(1);
		assertThat(second).isZero();
		ArticleRepository.ArticleSummaryTarget target = articleRepository
				.findSummaryTargetByArticleIdAndAnalysisStatus(
						article.getArticleId(), AnalysisStatus.COMPLETED)
				.orElseThrow();
		assertThat(target.getSummaryStatus()).isEqualTo(SummaryStatus.PROCESSING);
	}

	@Test
	void PROCESSING_상태에_생성된_요약과_생성시각을_저장한다() {
		NewsOrganization organization = entityManager.persist(new NewsOrganization("연합뉴스"));
		Article article = entityManager.persist(new Article(
				"요약 대상 기사",
				LocalDateTime.of(2026, 9, 17, 9, 0),
				organization,
				null,
				AnalysisStatus.COMPLETED));
		entityManager.flush();
		claimSummary(article.getArticleId());
		LocalDateTime generatedAt = LocalDateTime.of(2026, 9, 17, 10, 0);

		int updated = articleRepository.completeSummaryGeneration(
				article.getArticleId(),
				"생성된 기사 요약",
				generatedAt,
				SummaryStatus.PROCESSING,
				SummaryStatus.COMPLETED);
		entityManager.clear();

		assertThat(updated).isEqualTo(1);
		Object[] row = (Object[]) entityManager.getEntityManager().createNativeQuery(
					"SELECT summary, summary_status, summary_generated_at "
							+ "FROM articles WHERE article_id = ?1")
				.setParameter(1, article.getArticleId())
				.getSingleResult();
		assertThat(row[0]).isEqualTo("생성된 기사 요약");
		assertThat(row[1]).isEqualTo("COMPLETED");
		assertThat(row[2]).isNotNull();
	}

	@Test
	void 분석이_완료되지_않은_기사는_요약_생성을_선점할_수_없다() {
		NewsOrganization organization = entityManager.persist(new NewsOrganization("연합뉴스"));
		Article article = entityManager.persist(new Article(
				"분석 중인 기사",
				LocalDateTime.of(2026, 9, 17, 9, 0),
				organization,
				null,
				AnalysisStatus.PROCESSING));
		entityManager.flush();

		assertThat(claimSummary(article.getArticleId())).isZero();
	}

	@Test
	void articleId_목록으로_기사를_언론사와_함께_조회한다() {
		NewsOrganization org = entityManager.persist(new NewsOrganization("연합뉴스"));
		Article a1 = entityManager.persist(new Article("제목1", LocalDateTime.of(2024, 1, 11, 9, 0), org));
		Article a2 = entityManager.persist(new Article("제목2", LocalDateTime.of(2024, 1, 12, 9, 0), org));
		entityManager.persist(new Article("제목3", LocalDateTime.of(2024, 1, 13, 9, 0), org));
		entityManager.flush();
		entityManager.clear();

		List<Article> found = articleRepository.findAllWithOrganizationByArticleIdIn(
				List.of(a1.getArticleId(), a2.getArticleId()));

		assertThat(found).extracting(Article::getTitle).containsExactlyInAnyOrder("제목1", "제목2");
		assertThat(found).allSatisfy(a -> assertThat(a.getOrganization().getName()).isEqualTo("연합뉴스"));
	}

	@Test
	void 존재하지_않는_articleId면_빈_목록이다() {
		assertThat(articleRepository.findAllWithOrganizationByArticleIdIn(List.of(999L))).isEmpty();
	}

	@Test
	void 요청한_ID_중_COMPLETED_기사_ID만_반환한다() {
		NewsOrganization organization = entityManager.persist(new NewsOrganization("연합뉴스"));
		LocalDateTime publishedAt = LocalDateTime.of(2026, 9, 1, 9, 0);
		Article completed = entityManager.persist(new Article(
				"분석 완료", publishedAt, organization, null, AnalysisStatus.COMPLETED));
		Article processing = entityManager.persist(new Article(
				"분석 중", publishedAt, organization, null, AnalysisStatus.PROCESSING));
		entityManager.flush();

		List<Long> found = articleRepository.findArticleIdsByIdInAndAnalysisStatus(
				List.of(completed.getArticleId(), processing.getArticleId(), 999L),
				AnalysisStatus.COMPLETED);

		assertThat(found).containsExactly(completed.getArticleId());
	}

	@Test
	void findGraphRefByArticleId는_분석된_기사의_nodeId를_반환한다() {
		NewsOrganization org = entityManager.persist(new NewsOrganization("연합뉴스"));
		Article article = new Article("제목1", LocalDateTime.of(2024, 1, 11, 9, 0), org);
		ReflectionTestUtils.setField(article, "nodeId", "00000010-0920-4000-8000-000000000001");
		entityManager.persist(article);
		entityManager.flush();
		entityManager.clear();

		ArticleRepository.ArticleGraphRef ref = articleRepository
				.findGraphRefByArticleId(article.getArticleId()).orElseThrow();

		assertThat(ref.getNodeId()).isEqualTo("00000010-0920-4000-8000-000000000001");
	}

	@Test
	void findGraphRefByArticleId는_분석_전_기사면_nodeId가_null이다() {
		NewsOrganization org = entityManager.persist(new NewsOrganization("연합뉴스"));
		Article article = entityManager.persist(
				new Article("제목1", LocalDateTime.of(2024, 1, 11, 9, 0), org));
		entityManager.flush();
		entityManager.clear();

		ArticleRepository.ArticleGraphRef ref = articleRepository
				.findGraphRefByArticleId(article.getArticleId()).orElseThrow();

		// 기사 자체는 있으므로 빈 Optional 이 아니다. 둘을 구분해야 404 와 Neo4j 건너뛰기가 갈린다.
		assertThat(ref.getArticleId()).isEqualTo(article.getArticleId());
		assertThat(ref.getNodeId()).isNull();
	}

	@Test
	void findGraphRefByArticleId는_없는_기사면_빈_Optional이다() {
		assertThat(articleRepository.findGraphRefByArticleId(999L)).isEmpty();
	}

	private static final String COLLECTED_URL = "https://www.yna.co.kr/view/AKR20260914";

	private void insertCollected(Long orgId, String title, String url, String category) {
		articleRepository.insertIfAbsent(orgId, title, url, ArticleUrls.hash(url),
				LocalDateTime.of(2026, 9, 14, 14, 0), category, "본문입니다.",
				ContentType.FULL_TEXT.name(), AnalysisStatus.PROCESSING.name());
	}

	@Test
	void insertIfAbsent는_수집한_기사를_저장한다() {
		NewsOrganization org = entityManager.persist(new NewsOrganization("연합뉴스"));
		entityManager.flush();

		insertCollected(org.getId(), "기준금리 동결", COLLECTED_URL, "business");
		entityManager.clear();

		Long id = articleRepository.findIdByUrlHash(ArticleUrls.hash(COLLECTED_URL)).orElseThrow();
		Article found = articleRepository.findAllWithOrganizationByArticleIdIn(List.of(id)).get(0);
		assertThat(found.getTitle()).isEqualTo("기준금리 동결");
		assertThat(found.getUrl()).isEqualTo(COLLECTED_URL);
		assertThat(found.getContent()).isEqualTo("본문입니다.");
		assertThat(found.getContentType()).isEqualTo(ContentType.FULL_TEXT);
		assertThat(found.getSourceCategory()).isEqualTo("business");
		assertThat(found.getOrganization().getName()).isEqualTo("연합뉴스");
	}

	@Test
	void insertIfAbsent는_분류를_비워두고_분석_상태를_기본값으로_둔다() {
		// topic_code 는 분석 단계가 채우고, analysis_status 는 컬럼 기본값(PROCESSING)을 쓴다.
		NewsOrganization org = entityManager.persist(new NewsOrganization("연합뉴스"));
		entityManager.flush();

		insertCollected(org.getId(), "기준금리 동결", COLLECTED_URL, "business");
		entityManager.clear();

		Long id = articleRepository.findIdByUrlHash(ArticleUrls.hash(COLLECTED_URL)).orElseThrow();
		Article found = articleRepository.findAllWithOrganizationByArticleIdIn(List.of(id)).get(0);
		assertThat(found.getTopicCode()).isNull();
		assertThat(found.getAnalysisStatus()).isEqualTo(AnalysisStatus.PROCESSING);
		assertThat(found.getSummaryStatus()).isEqualTo(SummaryStatus.NOT_REQUESTED);
		assertThat(found.getNodeId()).isNull();
	}

	@Test
	void insertIfAbsent는_같은_기사를_다시_수집하면_건너뛴다() {
		NewsOrganization org = entityManager.persist(new NewsOrganization("연합뉴스"));
		entityManager.flush();
		insertCollected(org.getId(), "기준금리 동결", COLLECTED_URL, "business");
		entityManager.clear();

		insertCollected(org.getId(), "제목이 바뀌어도", COLLECTED_URL, "general");
		entityManager.clear();

		Long id = articleRepository.findIdByUrlHash(ArticleUrls.hash(COLLECTED_URL)).orElseThrow();
		Article found = articleRepository.findAllWithOrganizationByArticleIdIn(List.of(id)).get(0);
		assertThat(found.getTitle()).isEqualTo("기준금리 동결"); // 기존 값을 덮어쓰지 않는다
		assertThat(found.getSourceCategory()).isEqualTo("business");
	}

	@Test
	void insertIfAbsent는_추적_파라미터만_다른_같은_기사도_건너뛴다() {
		NewsOrganization org = entityManager.persist(new NewsOrganization("연합뉴스"));
		entityManager.flush();
		insertCollected(org.getId(), "기준금리 동결", COLLECTED_URL, "business");
		entityManager.clear();

		insertCollected(org.getId(), "같은 기사", COLLECTED_URL + "?utm_source=gnews", "general");
		entityManager.clear();

		// url 정규화로 해시가 같아 중복으로 걸린다.
		assertThat(articleRepository.findIdByUrlHash(
				ArticleUrls.hash(COLLECTED_URL + "?utm_source=gnews"))).isPresent();
	}

	@Test
	void insertIfAbsent는_다른_기사면_따로_저장한다() {
		NewsOrganization org = entityManager.persist(new NewsOrganization("연합뉴스"));
		entityManager.flush();
		String other = "https://www.yna.co.kr/view/AKR20260915";

		insertCollected(org.getId(), "기사 1", COLLECTED_URL, "business");
		insertCollected(org.getId(), "기사 2", other, "business");
		entityManager.clear();

		assertThat(articleRepository.findIdByUrlHash(ArticleUrls.hash(COLLECTED_URL)))
				.isNotEqualTo(articleRepository.findIdByUrlHash(ArticleUrls.hash(other)));
	}

	@Test
	void findIdByUrlHash는_저장되지_않은_기사면_빈_Optional이다() {
		assertThat(articleRepository.findIdByUrlHash(ArticleUrls.hash("https://없는.기사/1"))).isEmpty();
	}

	private int claimSummary(Long articleId) {
		return articleRepository.claimSummaryGeneration(
				articleId,
				AnalysisStatus.COMPLETED,
				SummaryStatus.PROCESSING,
				List.of(SummaryStatus.NOT_REQUESTED, SummaryStatus.FAILED));
	}
}
