package com.starlightnews.backend.domain.article.collect;

import java.time.Duration;
import java.time.LocalDateTime;
import java.util.List;

import com.starlightnews.backend.domain.article.dto.CollectedArticle;
import com.starlightnews.backend.domain.article.repository.ArticleRepository;
import com.starlightnews.backend.domain.article.service.ArticleStoreService;
import com.starlightnews.backend.domain.article.service.ArticleWriter;
import com.starlightnews.backend.domain.article.service.NewsOrganizationResolver;
import com.starlightnews.backend.domain.article.support.ArticleContents;
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
        var scheduler = new ArticleCollectScheduler(collector, new CollectedArticlePreprocessor(), store);
        scheduler.collect();
        Long firstId = repository.findIdByUrlHash(ArticleUrls.hash("https://crawl-test.example/1")).orElseThrow();
        Long thirdId = repository.findIdByUrlHash(ArticleUrls.hash("https://crawl-test.example/3")).orElseThrow();
        var saved = repository.findAllWithOrganizationByArticleIdIn(List.of(firstId, thirdId));
        assertThat(saved).hasSize(2).allSatisfy(article -> {
            assertThat(article.getPublishedAt()).isEqualTo(LocalDateTime.of(2026, 9, 15, 10, 0));
            assertThat(article.getContent()).isNotBlank();
            assertThat(article.getContentType()).isEqualTo(ContentType.FULL_TEXT);
        });
        assertThat(store.store(new CollectedArticlePreprocessor().process(collector.collectAll()))).isZero();
        assertThat(repository.findIdByUrlHash(ArticleUrls.hash("https://crawl-test.example/1"))).contains(firstId);
        server.verify();
    }

    /**
     * 사이트의 추천 기사 목록이 본문 자리에 들어오면, 회차마다 제목만 다른 기사가 쌓인다.
     * 전처리의 본문 중복 검사는 한 회차 안에서만 비교해서 이걸 막지 못한다.
     */
    @Test void 회차가_달라도_같은_본문에_제목이_다르면_저장하지_않는다() {
        String sharedBody = "[뉴스핌 베스트 기사] 사진 위고비에 도전한 새 비만약 '에페' 가격은?";

        assertThat(store.store(List.of(collected("아시안게임 남자 계영 800m", "list-1", sharedBody)))).isEqualTo(1);
        assertThat(store.store(List.of(collected("김여정 담화 발표", "list-2", sharedBody)))).isZero();

        assertThat(repository.findIdByUrlHash(ArticleUrls.hash("https://collision.example/list-2"))).isEmpty();
        assertThat(repository.findTitlesByContentHash(ArticleContents.hash(sharedBody)))
            .containsExactly("아시안게임 남자 계영 800m");
    }

    @Test void 제목까지_같으면_다른_매체가_받아쓴_기사로_보고_저장한다() {
        String wireBody = "정부가 추석 연휴 교통 대책을 발표했다.";

        assertThat(store.store(List.of(collected("추석 연휴 교통 대책 발표", "wire-1", wireBody)))).isEqualTo(1);
        assertThat(store.store(List.of(collected("추석 연휴 교통 대책 발표", "wire-2", wireBody)))).isEqualTo(1);
    }

    private static CollectedArticle collected(String title, String path, String content) {
        String url = "https://collision.example/" + path;
        return new CollectedArticle(title, url, ArticleUrls.hash(url),
            LocalDateTime.of(2026, 9, 15, 10, 0), content, ContentType.FULL_TEXT,
            "general", "뉴스핌", "newspim.com");
    }
}
