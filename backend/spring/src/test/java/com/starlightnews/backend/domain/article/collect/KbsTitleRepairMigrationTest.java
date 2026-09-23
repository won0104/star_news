package com.starlightnews.backend.domain.article.collect;

import java.util.List;
import java.util.Map;

import javax.sql.DataSource;

import com.starlightnews.backend.domain.article.support.ArticleContents;
import com.starlightnews.backend.domain.article.support.ArticleUrls;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.jdbc.AutoConfigureTestDatabase;
import org.springframework.boot.test.autoconfigure.orm.jpa.DataJpaTest;
import org.springframework.core.io.ClassPathResource;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.init.ResourceDatabasePopulator;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

import static org.assertj.core.api.Assertions.assertThat;

@DataJpaTest
@ActiveProfiles("test")
@AutoConfigureTestDatabase(replace = AutoConfigureTestDatabase.Replace.NONE)
@Transactional(propagation = Propagation.NOT_SUPPORTED)
class KbsTitleRepairMigrationTest {

	private static final String TARGET_URL = "https://news.kbs.co.kr/news/view.do?ncd=repair-test";
	private static final String COMPLETED_URL = "https://news.kbs.co.kr/news/view.do?ncd=completed-test";
	private static final String UNKNOWN_FORMAT_URL =
			"https://news.kbs.co.kr/news/view.do?ncd=unknown-format-test";

	@Autowired
	private JdbcTemplate jdbcTemplate;

	@Autowired
	private DataSource dataSource;

	@AfterEach
	void cleanUp() {
		jdbcTemplate.update("DELETE FROM articles WHERE url_hash IN (?, ?, ?)",
				ArticleUrls.hash(TARGET_URL), ArticleUrls.hash(COMPLETED_URL),
				ArticleUrls.hash(UNKNOWN_FORMAT_URL));
	}

	@Test
	void 분석_전_KBS_기사만_제목과_본문을_보정한다() {
		Long organizationId = kbsOrganizationId();
		String actualTitle = "이 대통령, 북핵 동결과 제재 완화 교환 제안";
		String body = "기사 본문 첫 문단입니다.\n기사 본문 둘째 문단입니다.";
		String legacyContent = actualTitle + "\r\n"
				+ "읽어주기 기능은 크롬기반의\r\n"
				+ "브라우저에서만 사용하실 수 있습니다.\r\n"
				+ body.replace("\n", "\r\n") + "\r\n"
				+ "■ 제보하기\r\n▷ 카카오톡 : 'KBS제보' 검색, 채널 추가";
		insertArticle(organizationId, TARGET_URL, legacyContent, "PROCESSING", "NOT_REQUESTED", null);
		insertArticle(organizationId, COMPLETED_URL, legacyContent, "COMPLETED", "COMPLETED", "기존 요약");
		String unknownFormatContent = actualTitle + "\n" + body;
		insertArticle(organizationId, UNKNOWN_FORMAT_URL, unknownFormatContent,
				"PROCESSING", "NOT_REQUESTED", null);

		ResourceDatabasePopulator migration = new ResourceDatabasePopulator(
				new ClassPathResource("db/migration/V15__repair_kbs_outlet_titles.sql"));
		migration.setSqlScriptEncoding("UTF-8");
		migration.execute(dataSource);

		Map<String, Object> repaired = findArticle(TARGET_URL);
		assertThat(repaired.get("title")).isEqualTo(actualTitle);
		assertThat(repaired.get("content")).isEqualTo(body);
		assertThat((byte[]) repaired.get("content_hash")).isEqualTo(ArticleContents.hash(body));

		Map<String, Object> completed = findArticle(COMPLETED_URL);
		assertThat(completed.get("title")).isEqualTo("KBS 뉴스");
		assertThat(completed.get("content")).isEqualTo(legacyContent);

		Map<String, Object> unknownFormat = findArticle(UNKNOWN_FORMAT_URL);
		assertThat(unknownFormat.get("title")).isEqualTo("KBS 뉴스");
		assertThat(unknownFormat.get("content")).isEqualTo(unknownFormatContent);
	}

	private Long kbsOrganizationId() {
		List<Long> ids = jdbcTemplate.query(
				"SELECT organization_id FROM news_organizations WHERE domain = ?",
				(rs, rowNum) -> rs.getLong(1), "news.kbs.co.kr");
		if (!ids.isEmpty()) {
			return ids.get(0);
		}
		jdbcTemplate.update(
				"INSERT INTO news_organizations (name, domain) VALUES (?, ?)",
				"KBS뉴스", "news.kbs.co.kr");
		return jdbcTemplate.queryForObject(
				"SELECT organization_id FROM news_organizations WHERE domain = ?",
				Long.class, "news.kbs.co.kr");
	}

	private void insertArticle(Long organizationId, String url, String content,
			String analysisStatus, String summaryStatus, String summary) {
		jdbcTemplate.update("""
				INSERT INTO articles (
				    organization_id, title, url, url_hash, published_at, content,
				    content_type, content_hash, summary, summary_status,
				    analysis_status, analysis_attempts
				) VALUES (?, 'KBS 뉴스', ?, ?, CURRENT_TIMESTAMP(6), ?,
				          'FULL_TEXT', ?, ?, ?, ?, 0)
				""",
				organizationId, url, ArticleUrls.hash(url), content,
				ArticleContents.hash(content), summary, summaryStatus, analysisStatus);
	}

	private Map<String, Object> findArticle(String url) {
		return jdbcTemplate.queryForMap(
				"SELECT title, content, content_hash FROM articles WHERE url_hash = ?",
				ArticleUrls.hash(url));
	}
}
