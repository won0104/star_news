package com.starlightnews.backend.domain.article.support;

import java.time.LocalDateTime;
import java.util.Optional;

import com.starlightnews.backend.domain.article.dto.CollectedArticle;
import com.starlightnews.backend.domain.article.dto.GNewsArticlesResponse.GNewsArticle;
import com.starlightnews.backend.domain.article.dto.GNewsArticlesResponse.Source;
import com.starlightnews.backend.global.enums.ContentType;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class GNewsArticleMapperTest {

	private static final Source YONHAP = new Source("연합뉴스", "https://www.yna.co.kr");
	private static final String URL = "https://www.yna.co.kr/view/AKR20260914";
	private static final String PUBLISHED_AT = "2026-09-14T05:00:00Z";

	private GNewsArticle article(String title, String content, String description) {
		return new GNewsArticle(title, description, content, URL, PUBLISHED_AT, YONHAP);
	}

	private CollectedArticle collected(GNewsArticle article) {
		return GNewsArticleMapper.toCollected(article, "business").orElseThrow();
	}

	@Test
	void 정상_기사를_수집_결과로_옮긴다() {
		CollectedArticle result = collected(article("기준금리 동결", "한국은행은 기준금리를 동결했다.", "요약"));

		assertThat(result.title()).isEqualTo("기준금리 동결");
		assertThat(result.url()).isEqualTo(URL);
		assertThat(result.content()).isEqualTo("한국은행은 기준금리를 동결했다.");
		assertThat(result.organizationName()).isEqualTo("연합뉴스");
		assertThat(result.organizationDomain()).isEqualTo("www.yna.co.kr");
		assertThat(result.urlHash()).isEqualTo(ArticleUrls.hash(URL));
	}

	@Test
	void UTC_발행시각을_KST_벽시계로_바꾼다() {
		CollectedArticle result = collected(article("제목", "본문", null));

		// 2026-09-14T05:00:00Z == 2026-09-14 14:00 KST
		assertThat(result.publishedAt()).isEqualTo(LocalDateTime.of(2026, 9, 14, 14, 0));
	}

	@Test
	void GNews_카테고리를_변환하지_않고_그대로_보존한다() {
		// topic_code 분류는 FastAPI 담당이라 수집 단계는 원본 분류만 남긴다.
		assertThat(collected(article("제목", "본문", null)).sourceCategory()).isEqualTo("business");
	}

	@Test
	void 잘림_표시가_없는_본문은_전문으로_본다() {
		assertThat(collected(article("제목", "한국은행은 기준금리를 동결했다.", null)).contentType())
				.isEqualTo(ContentType.FULL_TEXT);
	}

	@Test
	void 끝에_잘림_표시가_있으면_일부_본문으로_본다() {
		CollectedArticle result = collected(
				article("제목", "한국은행은 기준금리를... [1234 chars]", null));

		assertThat(result.contentType()).isEqualTo(ContentType.TRUNCATED_TEXT);
	}

	@Test
	void content가_비면_description을_본문으로_쓰고_제공처_요약으로_본다() {
		CollectedArticle result = collected(article("제목", null, "제공처가 준 요약문"));

		assertThat(result.content()).isEqualTo("제공처가 준 요약문");
		assertThat(result.contentType()).isEqualTo(ContentType.SOURCE_SUMMARY);
	}

	@Test
	void content와_description이_모두_비면_저장하지_않는다() {
		// articles.content 가 NOT NULL 이라 본문이 없으면 애초에 저장할 수 없다.
		assertThat(GNewsArticleMapper.toCollected(article("제목", null, null), "business")).isEmpty();
	}

	@Test
	void 제목이_없으면_저장하지_않는다() {
		assertThat(GNewsArticleMapper.toCollected(article("   ", "본문", null), "business")).isEmpty();
	}

	@Test
	void url이_없으면_저장하지_않는다() {
		GNewsArticle noUrl = new GNewsArticle("제목", null, "본문", null, PUBLISHED_AT, YONHAP);

		assertThat(GNewsArticleMapper.toCollected(noUrl, "business")).isEmpty();
	}

	@Test
	void 언론사가_없으면_저장하지_않는다() {
		// organization_id 가 NOT NULL 이라 언론사를 특정할 수 없으면 저장할 수 없다.
		GNewsArticle noSource = new GNewsArticle("제목", null, "본문", URL, PUBLISHED_AT, null);

		assertThat(GNewsArticleMapper.toCollected(noSource, "business")).isEmpty();
	}

	@Test
	void 발행시각을_해석할_수_없으면_저장하지_않는다() {
		GNewsArticle badTime = new GNewsArticle("제목", null, "본문", URL, "어제", YONHAP);

		assertThat(GNewsArticleMapper.toCollected(badTime, "business")).isEmpty();
	}

	@Test
	void 언론사_홈_주소가_없으면_domain은_null이다() {
		GNewsArticle noSourceUrl = new GNewsArticle(
				"제목", null, "본문", URL, PUBLISHED_AT, new Source("연합뉴스", null));

		assertThat(GNewsArticleMapper.toCollected(noSourceUrl, "business").orElseThrow()
				.organizationDomain()).isNull();
	}

	@Test
	void 제목이_500자를_넘으면_잘라서_저장한다() {
		// articles.title 이 VARCHAR(500) 이라 넘기면 INSERT 자체가 실패한다.
		String longTitle = "가".repeat(600);

		Optional<CollectedArticle> result = GNewsArticleMapper.toCollected(
				article(longTitle, "본문", null), "business");

		assertThat(result.orElseThrow().title()).hasSize(500);
	}
}
