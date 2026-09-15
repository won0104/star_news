package com.starlightnews.backend.domain.article.collect;

import java.time.Duration;
import java.time.LocalDateTime;
import java.util.List;

import com.starlightnews.backend.domain.article.repository.ArticleRepository;
import com.starlightnews.backend.domain.article.service.ArticleStoreService;
import com.starlightnews.backend.domain.article.service.ArticleWriter;
import com.starlightnews.backend.domain.article.service.NewsOrganizationResolver;
import com.starlightnews.backend.domain.article.support.ArticleUrls;
import com.starlightnews.backend.global.enums.ContentType;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.jdbc.AutoConfigureTestDatabase;
import org.springframework.boot.test.autoconfigure.orm.jpa.DataJpaTest;
import org.springframework.context.annotation.Import;
import org.springframework.http.MediaType;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestClient;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.queryParam;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withSuccess;

@DataJpaTest
@ActiveProfiles("test")
@AutoConfigureTestDatabase(replace = AutoConfigureTestDatabase.Replace.NONE)
@Import({ArticleStoreService.class, ArticleWriter.class, NewsOrganizationResolver.class})
class ArticleCollectionIntegrationTest {
    @Autowired ArticleStoreService store;
    @Autowired ArticleRepository repository;

    @Test void 중간_응답이_깨져도_정상_기사를_저장하고_재수집시_중복을_막는다() {
        var builder = RestClient.builder();
        var server = MockRestServiceServer.bindTo(builder).build();
        var properties = new GNewsProperties("https://gnews.example.test/api/v4", "fake-key", "ko", "kr", 12,
            List.of("general", "business", "sports"), Duration.ofSeconds(5), null);
        var client = new GNewsClient(builder.baseUrl(properties.baseUrl()).build(), properties);
        var collector = new ArticleCollectService(client, properties);
        for (int i = 0; i < 2; i++) {
            server.expect(queryParam("category", "general")).andRespond(withSuccess(GNewsResilienceTest.body("1"), MediaType.APPLICATION_JSON));
            server.expect(queryParam("category", "business")).andRespond(withSuccess("{bad-json", MediaType.APPLICATION_JSON));
            server.expect(queryParam("category", "sports")).andRespond(withSuccess(GNewsResilienceTest.body("3"), MediaType.APPLICATION_JSON));
        }
        var scheduler = new ArticleCollectScheduler(collector, store);
        scheduler.collect();
        Long firstId = repository.findIdByUrlHash(ArticleUrls.hash("https://crawl-test.example/1")).orElseThrow();
        Long thirdId = repository.findIdByUrlHash(ArticleUrls.hash("https://crawl-test.example/3")).orElseThrow();
        var saved = repository.findAllWithOrganizationByArticleIdIn(List.of(firstId, thirdId));
        assertThat(saved).hasSize(2).allSatisfy(article -> {
            assertThat(article.getPublishedAt()).isEqualTo(LocalDateTime.of(2026, 9, 15, 10, 0));
            assertThat(article.getContent()).isEqualTo("전문 본문입니다.");
            assertThat(article.getContentType()).isEqualTo(ContentType.FULL_TEXT);
        });
        assertThat(store.store(collector.collectAll())).isZero();
        assertThat(repository.findIdByUrlHash(ArticleUrls.hash("https://crawl-test.example/1"))).contains(firstId);
        server.verify();
    }
}
