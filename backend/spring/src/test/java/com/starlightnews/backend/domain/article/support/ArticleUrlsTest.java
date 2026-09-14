package com.starlightnews.backend.domain.article.support;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class ArticleUrlsTest {

	@Test
	void 스킴과_호스트를_소문자로_바꾼다() {
		assertThat(ArticleUrls.normalize("HTTPS://News.Example.COM/articles/1"))
				.isEqualTo("https://news.example.com/articles/1");
	}

	@Test
	void 경로의_대소문자는_바꾸지_않는다() {
		// 경로는 서버에 따라 대소문자를 구분하므로 건드리면 다른 기사를 같은 것으로 볼 수 있다.
		assertThat(ArticleUrls.normalize("https://news.example.com/Articles/AbC"))
				.isEqualTo("https://news.example.com/Articles/AbC");
	}

	@Test
	void 프래그먼트를_제거한다() {
		assertThat(ArticleUrls.normalize("https://news.example.com/articles/1#comments"))
				.isEqualTo("https://news.example.com/articles/1");
	}

	@Test
	void 추적_파라미터만_제거하고_나머지_쿼리는_남긴다() {
		assertThat(ArticleUrls.normalize(
				"https://news.example.com/read?sid=100&utm_source=gnews&utm_medium=rss&fbclid=xyz"))
				.isEqualTo("https://news.example.com/read?sid=100");
	}

	@Test
	void 쿼리가_추적_파라미터뿐이면_물음표도_남기지_않는다() {
		assertThat(ArticleUrls.normalize("https://news.example.com/read?utm_source=gnews"))
				.isEqualTo("https://news.example.com/read");
	}

	@Test
	void 앞뒤_공백을_제거한다() {
		assertThat(ArticleUrls.normalize("  https://news.example.com/articles/1  "))
				.isEqualTo("https://news.example.com/articles/1");
	}

	@Test
	void 파싱할_수_없는_값이면_공백만_제거해_돌려준다() {
		assertThat(ArticleUrls.normalize("  not a url  ")).isEqualTo("not a url");
	}

	@Test
	void hash는_32바이트_SHA256이다() {
		assertThat(ArticleUrls.hash("https://news.example.com/articles/1")).hasSize(32);
	}

	@Test
	void 추적_파라미터만_다른_주소는_같은_해시를_갖는다() {
		byte[] plain = ArticleUrls.hash("https://news.example.com/articles/1");
		byte[] tracked = ArticleUrls.hash("https://news.example.com/articles/1?utm_source=gnews");

		assertThat(tracked).isEqualTo(plain); // 같은 기사가 두 번 저장되지 않는다
	}

	@Test
	void 다른_기사는_다른_해시를_갖는다() {
		assertThat(ArticleUrls.hash("https://news.example.com/articles/2"))
				.isNotEqualTo(ArticleUrls.hash("https://news.example.com/articles/1"));
	}
}
