package com.starlightnews.backend.domain.article.collect;

import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.time.LocalDateTime;
import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.List;

import com.starlightnews.backend.domain.article.dto.CollectedArticle;
import com.starlightnews.backend.domain.article.exception.ArticleCollectErrorCode;
import com.starlightnews.backend.domain.article.service.ArticleStoreService;
import com.starlightnews.backend.global.enums.ContentType;
import com.starlightnews.backend.global.error.BusinessException;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.anyList;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class GNewsBackfillServiceTest {

	private static final OffsetDateTime FROM = OffsetDateTime.parse("2026-09-26T00:00:00Z");
	private static final OffsetDateTime TO = OffsetDateTime.parse("2026-09-27T00:00:00Z");

	/** 호출된 (카테고리, 구간, 페이지)를 순서대로 기록하는 가짜 클라이언트. */
	private static final class RecordingClient extends GNewsClient {

		private final List<String> calls = new ArrayList<>();
		private final int articlesPerCall;
		private ArticleCollectErrorCode failWith;
		private int failAfterCalls = Integer.MAX_VALUE;

		private RecordingClient(int articlesPerCall) {
			super(null, properties(), duration -> {
			});
			this.articlesPerCall = articlesPerCall;
		}

		@Override
		public List<CollectedArticle> fetchTopHeadlines(String category, Window window) {
			calls.add("%s|%s|%d".formatted(category, window.from(), window.page()));
			if (calls.size() > failAfterCalls && failWith != null) {
				throw new BusinessException(failWith);
			}
			List<CollectedArticle> articles = new ArrayList<>();
			for (int index = 0; index < articlesPerCall; index++) {
				articles.add(article(category + window.page() + index));
			}
			return articles;
		}
	}

	private static GNewsProperties properties() {
		return new GNewsProperties("https://gnews.example.io/api/v4", "key", "ko", "kr", 2,
				List.of("general", "business"), Duration.ofSeconds(5), null);
	}

	/**
	 * 전처리를 통과하는 기사를 만든다.
	 *
	 * <p>본문이 200자 미만이면 전처리가 버리고, 본문이 서로 같으면 제목이 다른 중복으로 보고 함께
	 * 버린다. 그래서 seed 로 본문을 서로 다르게 하고 길이를 채운다.
	 */
	private static CollectedArticle article(String seed) {
		String content = ("%s 구간 백필로 받아 온 기사 본문이다. ".formatted(seed)).repeat(12);
		return new CollectedArticle("제목 " + seed, "https://news.example.com/" + seed,
				seed.getBytes(StandardCharsets.UTF_8), LocalDateTime.of(2026, 9, 26, 12, 0),
				content, ContentType.FULL_TEXT, "general", "연합뉴스", "yna.co.kr");
	}

	private GNewsBackfillService service(RecordingClient client, GNewsBackfillProperties backfill,
			ArticleStoreService store) {
		CollectedArticlePreprocessor preprocessor = new CollectedArticlePreprocessor();
		return new GNewsBackfillService(client, preprocessor, store, properties(), backfill);
	}

	private GNewsBackfillProperties backfill(Duration slice, int maxPages) {
		return new GNewsBackfillProperties(true, FROM, TO, slice, maxPages);
	}

	@Test
	void 구간을_slice_단위로_쪼개_최신부터_훑는다() {
		// 24시간을 6시간으로 쪼개면 4구간. 최신 구간(18:00)이 먼저 나와야 한다.
		RecordingClient client = new RecordingClient(0);
		ArticleStoreService store = mock(ArticleStoreService.class);

		service(client, backfill(Duration.ofHours(6), 1), store).backfill();

		assertThat(client.calls).containsExactly(
				"general|2026-09-26T18:00Z|1", "business|2026-09-26T18:00Z|1",
				"general|2026-09-26T12:00Z|1", "business|2026-09-26T12:00Z|1",
				"general|2026-09-26T06:00Z|1", "business|2026-09-26T06:00Z|1",
				"general|2026-09-26T00:00Z|1", "business|2026-09-26T00:00Z|1");
	}

	@Test
	void 마지막_구간은_남은_길이만큼만_잡는다() {
		// 24시간을 10시간으로 쪼개면 10+10+4 로 3구간이 되고, 시작 시각 앞으로 넘어가지 않는다.
		RecordingClient client = new RecordingClient(0);

		service(client, backfill(Duration.ofHours(10), 1), mock(ArticleStoreService.class)).backfill();

		assertThat(client.calls).containsExactly(
				"general|2026-09-26T14:00Z|1", "business|2026-09-26T14:00Z|1",
				"general|2026-09-26T04:00Z|1", "business|2026-09-26T04:00Z|1",
				"general|2026-09-26T00:00Z|1", "business|2026-09-26T00:00Z|1");
	}

	@Test
	void 응답이_max만큼_꽉_차면_다음_페이지를_부른다() {
		// max 가 2인데 2건이 왔으면 아직 남았다고 보고 2페이지를 부른다. 상한은 2장이다.
		RecordingClient client = new RecordingClient(2);

		service(client, backfill(Duration.ofHours(24), 2), mock(ArticleStoreService.class)).backfill();

		assertThat(client.calls).containsExactly(
				"general|2026-09-26T00:00Z|1", "general|2026-09-26T00:00Z|2",
				"business|2026-09-26T00:00Z|1", "business|2026-09-26T00:00Z|2");
	}

	@Test
	void 응답이_max보다_적으면_다음_페이지를_부르지_않는다() {
		RecordingClient client = new RecordingClient(1);

		service(client, backfill(Duration.ofHours(24), 3), mock(ArticleStoreService.class)).backfill();

		assertThat(client.calls).containsExactly(
				"general|2026-09-26T00:00Z|1", "business|2026-09-26T00:00Z|1");
	}

	@Test
	void 요청_한도가_소진되면_남은_구간을_부르지_않는다() {
		// 한도 소진은 남은 카테고리·구간도 전부 실패한다. 요청을 더 태우지 않아야 한다.
		RecordingClient client = new RecordingClient(0);
		client.failWith = ArticleCollectErrorCode.NEWS_SOURCE_QUOTA_EXCEEDED;
		client.failAfterCalls = 1;

		service(client, backfill(Duration.ofHours(6), 1), mock(ArticleStoreService.class)).backfill();

		assertThat(client.calls).hasSize(2);
	}

	@Test
	void 구간이_거꾸로면_실행하지_않는다() {
		RecordingClient client = new RecordingClient(0);
		GNewsBackfillProperties reversed =
				new GNewsBackfillProperties(true, TO, FROM, Duration.ofHours(6), 1);

		int stored = service(client, reversed, mock(ArticleStoreService.class)).backfill();

		assertThat(stored).isZero();
		assertThat(client.calls).isEmpty();
	}

	@Test
	void 저장한_신규_건수를_합쳐_반환한다() {
		RecordingClient client = new RecordingClient(1);
		ArticleStoreService store = mock(ArticleStoreService.class);
		when(store.store(anyList())).thenReturn(3);

		// 6시간 slice 면 4구간이라 구간마다 3건씩 저장된 것으로 센다.
		int stored = service(client, backfill(Duration.ofHours(6), 1), store).backfill();

		assertThat(stored).isEqualTo(12);
	}
}
