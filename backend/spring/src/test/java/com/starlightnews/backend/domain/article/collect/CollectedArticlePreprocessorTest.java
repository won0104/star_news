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
	private static final String REAL_CONTENT = "본문입니다. ".repeat(100).strip();

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
		// 본문은 기사마다 달라야 한다. 같으면 수집 오류로 보고 버린다.
		assertThat(titlesAfter(
				article("첫 기사", REAL_CONTENT + " 하나"),
				article("[인사] 보건복지부", REAL_CONTENT + " 둘"),
				article("둘째 기사", REAL_CONTENT + " 셋")))
				.containsExactly("첫 기사", "둘째 기사");
	}

	@Test
	void 빈_목록이면_빈_목록이다() {
		assertThat(preprocessor.process(List.of())).isEmpty();
	}

	// --- 제목 보정 ---

	private CollectedArticle fromOutlet(String title, String outlet, String content) {
		return new CollectedArticle(title, "https://news.test/" + title.hashCode(),
				new byte[] {1}, LocalDateTime.of(2026, 9, 16, 9, 0), content,
				ContentType.FULL_TEXT, "general", outlet, "news.test");
	}

	private String repairedTitle(CollectedArticle article) {
		return preprocessor.process(List.of(article)).get(0).title();
	}

	@Test
	void 제목이_언론사명이면_본문에서_찾아_채운다() {
		String content = "한화, 19년 만에 한국시리즈 진출…문동주 PO MVP\n" + REAL_CONTENT;

		assertThat(repairedTitle(fromOutlet("KBS 뉴스", "KBS뉴스", content)))
				.isEqualTo("한화, 19년 만에 한국시리즈 진출…문동주 PO MVP");
	}

	@Test
	void 공백만_다른_언론사명도_같은_것으로_본다() {
		// KBS뉴스 vs KBS 뉴스. 그대로 비교하면 실측 171건 중 하나도 안 걸린다.
		String content = "손흥민 프리킥 데뷔골 ‘MLS 올해의 골’ 선정\n" + REAL_CONTENT;

		assertThat(repairedTitle(fromOutlet("KBS 뉴스", "KBS뉴스", content)))
				.isEqualTo("손흥민 프리킥 데뷔골 ‘MLS 올해의 골’ 선정");
	}

	@Test
	void 사이트_문구를_건너뛰고_제목을_찾는다() {
		String content = "AD\n기사 본문 영역\n정치\n트럼프·젠슨황에 가렸지만…APEC 진짜 주인공 ‘AI’\n" + REAL_CONTENT;

		assertThat(repairedTitle(fromOutlet("KBS 뉴스", "KBS뉴스", content)))
				.isEqualTo("트럼프·젠슨황에 가렸지만…APEC 진짜 주인공 ‘AI’");
	}

	@Test
	void 바이라인으로_시작하면_보정하지_않는다() {
		// 통신사 기사는 본문에 제목이 없다. 리드 문장을 제목으로 쓰면 분석이 잘못된 신호를 받는다.
		String content = "(서울=연합뉴스) 이주영 기자 = 당뇨병 전단계에 있는 사람들이 생활습관을 개선하면\n" + REAL_CONTENT;

		assertThat(repairedTitle(fromOutlet("연합뉴스 한민족센터", "연합뉴스 한민족센터", content)))
				.isEqualTo("연합뉴스 한민족센터");
	}

	@Test
	void 본문_문장으로_시작하면_보정하지_않는다() {
		String content = "국립암센터는 지난 12월 27일 중국 시안국제의학센터와 협약을 체결했다.\n" + REAL_CONTENT;

		assertThat(repairedTitle(fromOutlet("메디포뉴스", "메디포뉴스", content)))
				.isEqualTo("메디포뉴스");
	}

	@Test
	void 너무_긴_줄은_제목으로_쓰지_않는다() {
		// 실측한 정상 제목의 99%가 64자 이하다.
		String tooLong = "가".repeat(71);

		assertThat(repairedTitle(fromOutlet("메디포뉴스", "메디포뉴스", tooLong + "\n" + REAL_CONTENT)))
				.isEqualTo("메디포뉴스");
	}

	@Test
	void 물음표로_끝나는_제목은_살린다() {
		// "…과제는?" 처럼 끝나는 제목이 흔하다. 평서문 종결만 본문으로 본다.
		String content = "TK신공항 ‘2조 원 선투입’ 제안…실현 가능성과 과제는?\n" + REAL_CONTENT;

		assertThat(repairedTitle(fromOutlet("KBS 뉴스", "KBS뉴스", content)))
				.isEqualTo("TK신공항 ‘2조 원 선투입’ 제안…실현 가능성과 과제는?");
	}

	@Test
	void 제목이_정상이면_건드리지_않는다() {
		String content = "엉뚱한 첫 줄\n" + REAL_CONTENT;

		assertThat(repairedTitle(fromOutlet("기준금리 동결", "연합뉴스", content)))
				.isEqualTo("기준금리 동결");
	}

	// --- 본문 정리 ---

	private String cleanedContent(String content) {
		return preprocessor.process(List.of(article("제목", content))).get(0).content();
	}

	@Test
	void 앞머리_사이트_문구를_지운다() {
		String content = "AD\n기사 본문 영역\n정치\n" + REAL_CONTENT;

		assertThat(cleanedContent(content)).isEqualTo(REAL_CONTENT.strip());
	}

	@Test
	void 꼬리의_저작권_문구를_지운다() {
		// 저작권 표현은 매체마다 달라 목록이 아니라 패턴으로 잡는다.
		String content = REAL_CONTENT + "\n<저작권자 © 스타뉴스, 무단전재 및 재배포 금지>";

		assertThat(cleanedContent(content)).isEqualTo(REAL_CONTENT.strip());
	}

	@ParameterizedTest
	@ValueSource(strings = {
			"[저작권자(c) YTN 무단전재, 재배포 및 AI 데이터 활용 금지]",
			"Copyright ⓒ 세계일보. 무단 전재 및 재배포 금지",
			"※ 저작권자 ⓒ 파이낸셜뉴스, 무단전재-재배포 금지",
			"▶제보는 카톡 okjebo",
			"소셜 댓글",
			"더보기",
			"공유하기",
			"0",
			"*면책 조항: 이 기사는 투자 참고용으로 손실 책임을 지지 않습니다."
	})
	void 매체마다_다른_꼬리_문구를_지운다(String tail) {
		assertThat(cleanedContent(REAL_CONTENT + "\n" + tail)).isEqualTo(REAL_CONTENT.strip());
	}

	@Test
	void 꼬리가_여러_줄이어도_끝까지_지운다() {
		// 실측에서 저작권 문구 뒤에 댓글 수와 UI 문구가 더 붙는 경우가 있었다.
		String content = REAL_CONTENT + "\n공유하기\n0\n<저작권자 © 스타뉴스, 무단전재 금지>";

		assertThat(cleanedContent(content)).isEqualTo(REAL_CONTENT.strip());
	}

	@Test
	void 본문_가운데의_같은_문구는_건드리지_않는다() {
		// 앞뒤에서만 걷어낸다. 가운데를 지우면 문맥이 끊긴다.
		String content = "첫 문단입니다. " + "가".repeat(150) + "\n저작권 소송이 제기됐다.\n" + "나".repeat(150);

		assertThat(cleanedContent(content)).contains("저작권 소송이 제기됐다.");
	}

	@Test
	void 지나치게_많이_줄면_원본을_유지한다() {
		// 규칙이 본문까지 먹은 경우다. 실측에서 가장 많이 깎인 것도 81% 였다.
		String content = "짧은 본문입니다. " + "가".repeat(190) + "\n" + "저작권 ".repeat(60);

		assertThat(cleanedContent(content)).isEqualTo(content);
	}

	@Test
	void 줄바꿈이_없으면_손대지_않는다() {
		// 실측에 줄바꿈 없는 기사가 있었다. 문장 중간을 자르려다 본문을 훼손하지 않는다.
		String content = REAL_CONTENT.replace("\n", " ");

		assertThat(cleanedContent(content)).isEqualTo(content);
	}

	@Test
	void 정리할_것이_없으면_원본_그대로다() {
		assertThat(cleanedContent(REAL_CONTENT)).isEqualTo(REAL_CONTENT.strip());
	}

	@Test
	void 제목_보정이_본문_정리보다_먼저다() {
		// 본문 정리가 "기사 본문 영역" 을 먼저 지우면 제목을 찾을 단서가 사라진다.
		String content = "기사 본문 영역\n한화, 19년 만에 한국시리즈 진출\n" + REAL_CONTENT;
		CollectedArticle after = preprocessor.process(
				List.of(fromOutlet("KBS 뉴스", "KBS뉴스", content))).get(0);

		assertThat(after.title()).isEqualTo("한화, 19년 만에 한국시리즈 진출");
		assertThat(after.content()).doesNotContain("기사 본문 영역");
	}

	// --- 본문 동일 수집 오류 ---

	private CollectedArticle withUrl(String title, String url, String content) {
		return new CollectedArticle(title, url, url.getBytes(),
				LocalDateTime.of(2026, 9, 16, 9, 0), content,
				ContentType.FULL_TEXT, "general", "뉴스핌", "newspim.com");
	}

	@Test
	void 본문이_같은데_제목이_다르면_전부_버린다() {
		// 제공처가 기사 본문 대신 사이트의 인기 기사 영역을 긁어 온 경우다.
		// 어느 제목이 그 본문의 주인인지 알 수 없어 하나도 남기지 않는다.
		assertThat(titlesAfter(
				withUrl("김하성, 2타수 무안타", "https://newspim.com/1", REAL_CONTENT),
				withUrl("美 공군장관 우주 통제 무기 발언", "https://newspim.com/2", REAL_CONTENT),
				withUrl("올림픽 대표팀 명단 발표", "https://newspim.com/3", REAL_CONTENT)))
				.isEmpty();
	}

	@Test
	void 본문도_제목도_같으면_남긴다() {
		// 통신사 기사를 여러 매체가 받아쓴 것이라 정상이다. 실측에서 33그룹 67건이 여기 해당했다.
		assertThat(titlesAfter(
				withUrl("수성이 이렇게 줄었다고?", "https://a.test/1", REAL_CONTENT),
				withUrl("수성이 이렇게 줄었다고?", "https://b.test/2", REAL_CONTENT)))
				.containsExactly("수성이 이렇게 줄었다고?", "수성이 이렇게 줄었다고?");
	}

	@Test
	void 본문이_다르면_제목이_같아도_남긴다() {
		assertThat(titlesAfter(
				withUrl("같은 제목", "https://a.test/1", REAL_CONTENT),
				withUrl("같은 제목", "https://b.test/2", REAL_CONTENT + " 다른 내용")))
				.hasSize(2);
	}

	@Test
	void 충돌한_기사만_버리고_나머지는_지킨다() {
		assertThat(titlesAfter(
				withUrl("멀쩡한 기사", "https://a.test/0", REAL_CONTENT + " 고유"),
				withUrl("충돌 A", "https://newspim.com/1", REAL_CONTENT),
				withUrl("충돌 B", "https://newspim.com/2", REAL_CONTENT)))
				.containsExactly("멀쩡한 기사");
	}

	@Test
	void 군더더기만_다른_기사도_같은_본문으로_본다() {
		// 본문 정리를 마친 뒤에 비교하므로, 저작권 문구만 다른 기사도 충돌로 잡힌다.
		assertThat(titlesAfter(
				withUrl("충돌 A", "https://a.test/1", REAL_CONTENT + "\n<저작권자 © 스타뉴스>"),
				withUrl("충돌 B", "https://b.test/2", REAL_CONTENT + "\n더보기")))
				.isEmpty();
	}

	@Test
	void 보정해도_나머지_값은_그대로다() {
		String content = "진짜 제목입니다\n" + REAL_CONTENT;
		CollectedArticle before = fromOutlet("KBS 뉴스", "KBS뉴스", content);

		CollectedArticle after = preprocessor.process(List.of(before)).get(0);

		assertThat(after.url()).isEqualTo(before.url());
		assertThat(after.urlHash()).isEqualTo(before.urlHash());
		assertThat(after.content()).isEqualTo(before.content());
		assertThat(after.publishedAt()).isEqualTo(before.publishedAt());
		assertThat(after.organizationName()).isEqualTo(before.organizationName());
		assertThat(after.sourceCategory()).isEqualTo(before.sourceCategory());
	}
}
