package com.starlightnews.backend.domain.article.collect;

import java.time.LocalDateTime;
import java.util.List;

import com.starlightnews.backend.domain.article.dto.CollectedArticle;
import com.starlightnews.backend.global.enums.ContentType;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

import static org.assertj.core.api.Assertions.assertThat;

class CollectedArticlePreprocessorTest {

	private final CollectedArticlePreprocessor preprocessor = new CollectedArticlePreprocessor();

	/** 실측한 정상 기사의 최소가 500자 안팎이라, 통과해야 하는 본문은 그 정도로 만든다. */
	private static final String REAL_CONTENT = "본문입니다. ".repeat(100);

	private CollectedArticle article(String title, String content) {
		return new CollectedArticle(title, "https://news.test/" + title.hashCode(),
				new byte[] {1}, LocalDateTime.of(2026, 9, 16, 9, 0), content,
				ContentType.FULL_TEXT, "general", "테스트일보", "news.test");
	}

	private List<String> titlesAfter(CollectedArticle... articles) {
		return preprocessor.process(List.of(articles)).stream()
				.map(CollectedArticle::title)
				.toList();
	}

	@Test
	void 정상_기사는_그대로_통과한다() {
		assertThat(titlesAfter(article("기준금리 동결", REAL_CONTENT))).containsExactly("기준금리 동결");
	}

	@Test
	void 본문이_비면_제외한다() {
		// 실측에서 본문이 0자인 기사가 나왔다. 분석할 내용이 없다.
		assertThat(titlesAfter(article("본문 없는 기사", ""))).isEmpty();
	}

	@Test
	void 본문이_null이어도_깨지지_않는다() {
		assertThat(titlesAfter(article("본문 없는 기사", null))).isEmpty();
	}

	@Test
	void 속보_한_줄짜리는_제외한다() {
		// 65자짜리 속보가 실측에서 나왔다. Event 를 만들 수 없다.
		assertThat(titlesAfter(article("[속보] 지진 이후 원전 이상 없음", "지진 이후 현재까지 원전에 이상은 확인되지 않았다."))).isEmpty();
	}

	@Test
	void 길이_경계에서_정상_기사를_지키는지() {
		// 실측 정상 기사의 최소가 501자다. 임계값 200자면 여유가 충분하다.
		String justOver = "가".repeat(200);
		String justUnder = "가".repeat(199);

		assertThat(titlesAfter(article("통과", justOver))).containsExactly("통과");
		assertThat(titlesAfter(article("제외", justUnder))).isEmpty();
	}

	@ParameterizedTest
	@ValueSource(strings = {"[인사] 보건복지부", "[부고] 홍길동 별세", "[동정] 아무개 취임", "[신간] 어떤 책"})
	void 명단성_기사는_제외한다(String title) {
		assertThat(titlesAfter(article(title, REAL_CONTENT))).isEmpty();
	}

	@ParameterizedTest
	@ValueSource(strings = {
			"[오늘의 운세] 2026년 09월 15일 띠별 운세",
			"[지윤철학원의 오늘의 운세] 2026년 9월 15일 화요일 띠별 운세",
			"9월 15일(음력 8월 5일) 오늘의 운세"
	})
	void 운세는_길어도_제외한다(String title) {
		// 운세는 띠별로 12개를 적어 2,400~6,500자다. 길이로는 못 거른다.
		assertThat(titlesAfter(article(title, REAL_CONTENT))).isEmpty();
	}

	@Test
	void 제목_가운데_인사가_있는_기사는_남긴다() {
		// 접두사로만 본다. 부분 일치로 거르면 정상 기사가 날아간다.
		assertThat(titlesAfter(article("대통령실 인사 개편 단행", REAL_CONTENT)))
				.containsExactly("대통령실 인사 개편 단행");
	}

	@Test
	void 운세_산업_기사는_남긴다() {
		// "운세" 부분 일치로 걸면 이런 기사가 사라진다.
		assertThat(titlesAfter(article("운세 앱 시장 규제 강화된다", REAL_CONTENT)))
				.containsExactly("운세 앱 시장 규제 강화된다");
	}

	@Test
	void 시황_기사는_아직_남긴다() {
		// 경제 신호로 쓸 여지가 있어 판단을 미뤘다.
		assertThat(titlesAfter(article("[아침 시황] 비트코인 1억596만원", REAL_CONTENT)))
				.containsExactly("[아침 시황] 비트코인 1억596만원");
	}

	@Test
	void 제목이_null이어도_깨지지_않는다() {
		assertThat(preprocessor.process(List.of(article("정상", REAL_CONTENT)))).hasSize(1);
	}

	@Test
	void 남길_것과_버릴_것이_섞여도_순서를_지킨다() {
		assertThat(titlesAfter(
				article("첫 기사", REAL_CONTENT),
				article("[인사] 보건복지부", REAL_CONTENT),
				article("둘째 기사", REAL_CONTENT)))
				.containsExactly("첫 기사", "둘째 기사");
	}

	@Test
	void 빈_목록이면_빈_목록이다() {
		assertThat(preprocessor.process(List.of())).isEmpty();
	}
}
