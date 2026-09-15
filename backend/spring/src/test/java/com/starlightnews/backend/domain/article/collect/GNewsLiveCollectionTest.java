package com.starlightnews.backend.domain.article.collect;

import java.time.Duration;
import java.util.List;
import java.util.stream.Collectors;

import com.starlightnews.backend.domain.article.dto.CollectedArticle;
import com.starlightnews.backend.domain.article.service.ArticleStoreService;
import com.starlightnews.backend.domain.article.service.ArticleWriter;
import com.starlightnews.backend.domain.article.service.NewsOrganizationResolver;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.jdbc.AutoConfigureTestDatabase;
import org.springframework.boot.test.autoconfigure.orm.jpa.DataJpaTest;
import org.springframework.context.annotation.Import;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.web.client.RestClient;
import com.starlightnews.backend.global.client.HttpClients;

import static org.assertj.core.api.Assertions.assertThat;

/** 명시적으로 실행할 때만 실제 API를 1회 호출한다. 저장은 Testcontainers DB에서 롤백된다. */
@DataJpaTest(showSql = false)
@ActiveProfiles("test")
@AutoConfigureTestDatabase(replace = AutoConfigureTestDatabase.Replace.NONE)
@Import({ArticleStoreService.class, ArticleWriter.class, NewsOrganizationResolver.class})
@EnabledIfEnvironmentVariable(named = "GNEWS_LIVE_TEST", matches = "true")
class GNewsLiveCollectionTest {
    @Autowired ArticleStoreService store;

    @Test void 실제_기사_두_건을_수집하고_테스트DB에서_중복을_확인한다() {
        String key = System.getenv("GNEWS_API_KEY");
        assertThat(key != null && !key.isBlank()).as("GNEWS_API_KEY configured").isTrue();
        var properties = new GNewsProperties("https://gnews.io/api/v4", key, "ko", "kr", 2,
            List.of("business"), Duration.ofSeconds(10), null);
        var http = HttpClients.create(RestClient.builder(), properties.baseUrl(), properties.timeout());
        var articles = new ArticleCollectService(new GNewsClient(http, properties), properties).collectAll();
        assertThat(articles).isNotEmpty().hasSizeLessThanOrEqualTo(2);
        assertThat(articles).allSatisfy(article -> assertThat(article.content()).isNotBlank());
        assertThat(store.store(articles)).isEqualTo(articles.size());
        assertThat(store.store(articles)).isZero();
        System.out.println("Live GNews verification: articles=" + articles.size() + ", contentTypes="
            + articles.stream().collect(Collectors.groupingBy(CollectedArticle::contentType, Collectors.counting())));
    }
}
