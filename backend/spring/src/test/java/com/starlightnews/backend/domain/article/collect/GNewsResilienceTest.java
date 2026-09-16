package com.starlightnews.backend.domain.article.collect;

import java.io.IOException;
import java.time.Duration;
import java.util.List;

import com.starlightnews.backend.domain.article.dto.CollectedArticle;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestClient;

import static org.assertj.core.api.Assertions.*;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.*;
import static org.springframework.test.web.client.response.MockRestResponseCreators.*;

/** 제공처가 흔들릴 때 한 회차가 통째로 무너지지 않는지 본다. */
class GNewsResilienceTest {
    private final GNewsTestSleeper sleeper = new GNewsTestSleeper();
    private final GNewsProperties properties = new GNewsProperties(
        "https://gnews.example.test/api/v4", "fake-key", "ko", "kr", 12,
        List.of("general", "business", "sports"), Duration.ofSeconds(5), null);
    private MockRestServiceServer server;
    private GNewsClient client;
    private RestClient restClient;

    @BeforeEach void setUp() {
        var builder = RestClient.builder();
        server = MockRestServiceServer.bindTo(builder).build();
        restClient = builder.baseUrl(properties.baseUrl()).build();
        client = new GNewsClient(restClient, properties, sleeper);
    }

    /**
     * 실측한 정상 기사의 최소 길이가 500자 안팎이라 픽스처도 그만큼 길게 둔다.
     * 기사마다 본문이 달라야 한다. 같으면 전처리가 수집 오류로 보고 버린다.
     */
    static String content(String id) {
        return "%s번 기사 본문입니다.".formatted(id).repeat(30);
    }

    static String body(String id) {
        return """
            {"articles":[null,{"title":"기사 %s","content":"%s",
            "url":"https://crawl-test.example/%s","publishedAt":"2026-09-15T01:00:00Z",
            "source":{"name":"수집 통합 테스트 언론사","url":"https://crawl-test.example"}},null]}
            """.formatted(id, content(id), id);
    }

    @Test void 속도_제한은_두_번까지_재시도해서_복구한다() {
        server.expect(queryParam("category", "business")).andRespond(withStatus(HttpStatus.TOO_MANY_REQUESTS));
        server.expect(queryParam("category", "business")).andRespond(withStatus(HttpStatus.TOO_MANY_REQUESTS));
        server.expect(queryParam("category", "business")).andRespond(withSuccess(body("1"), MediaType.APPLICATION_JSON));
        assertThat(client.fetchTopHeadlines("business")).hasSize(1);
        assertThat(sleeper.waits).containsExactly(Duration.ofSeconds(1), Duration.ofSeconds(2));
        server.verify();
    }

    @Test void 재시도를_소진해도_다음_카테고리는_수집한다() {
        for (int i = 0; i < 3; i++) {
            server.expect(queryParam("category", "general")).andRespond(withStatus(HttpStatus.TOO_MANY_REQUESTS));
        }
        server.expect(queryParam("category", "business")).andRespond(withSuccess(body("2"), MediaType.APPLICATION_JSON));
        server.expect(queryParam("category", "sports")).andRespond(withSuccess(body("3"), MediaType.APPLICATION_JSON));
        assertThat(new ArticleCollectService(client, properties).collectAll())
            .extracting(CollectedArticle::title).containsExactly("기사 2", "기사 3");
        server.verify();
    }

    @ParameterizedTest
    @ValueSource(ints = {401, 403})
    void 인증_실패나_일일_한도면_부분_결과를_보존하고_중단한다(int status) {
        // 남은 카테고리도 같은 이유로 전부 실패한다. 요청을 더 태우지 않고 그때까지 모은 것을 살린다.
        server.expect(queryParam("category", "general")).andRespond(withSuccess(body("1"), MediaType.APPLICATION_JSON));
        server.expect(queryParam("category", "business")).andRespond(withStatus(HttpStatus.valueOf(status)));
        assertThat(new ArticleCollectService(client, properties).collectAll())
            .extracting(CollectedArticle::title).containsExactly("기사 1");
        server.verify();
    }

    @ParameterizedTest
    @ValueSource(strings = {"{invalid-json", "{\"articles\":123}", "<html>bad gateway</html>"})
    void 잘못된_응답은_해당_카테고리만_건너뛴다(String response) {
        server.expect(queryParam("category", "general")).andRespond(withSuccess(body("1"), MediaType.APPLICATION_JSON));
        server.expect(queryParam("category", "business")).andRespond(withSuccess(response, MediaType.APPLICATION_JSON));
        server.expect(queryParam("category", "sports")).andRespond(withSuccess(body("3"), MediaType.APPLICATION_JSON));
        assertThat(new ArticleCollectService(client, properties).collectAll())
            .extracting(CollectedArticle::title).containsExactly("기사 1", "기사 3");
        server.verify();
    }

    @Test void 네트워크_오류도_다음_카테고리를_막지_않는다() {
        server.expect(anything()).andRespond(withException(new IOException("connection lost")));
        server.expect(anything()).andRespond(withSuccess(body("2"), MediaType.APPLICATION_JSON));
        server.expect(anything()).andRespond(withSuccess(body("3"), MediaType.APPLICATION_JSON));
        assertThat(new ArticleCollectService(client, properties).collectAll()).hasSize(2);
        server.verify();
    }

    @Test void 대기_중_인터럽트면_재시도와_남은_수집을_중단한다() {
        client = new GNewsClient(restClient, properties, duration -> { throw new InterruptedException(); });
        server.expect(anything()).andRespond(withStatus(HttpStatus.TOO_MANY_REQUESTS));
        try {
            assertThat(new ArticleCollectService(client, properties).collectAll()).isEmpty();
            assertThat(Thread.currentThread().isInterrupted()).isTrue();
            server.verify();
        } finally {
            Thread.interrupted();
        }
    }
}
