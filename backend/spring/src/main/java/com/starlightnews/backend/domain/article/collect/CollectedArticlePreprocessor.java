package com.starlightnews.backend.domain.article.collect;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Locale;
import java.util.Set;
import java.util.regex.Pattern;
import java.util.stream.Collectors;

import com.starlightnews.backend.domain.article.dto.CollectedArticle;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

/**
 * 수집한 기사를 저장 전에 다듬는다.

 * <p>여기서 버린 기사는 저장되지 않는다. 버린 건 전부 로그에 기록한다.
 */
@Slf4j
@Component
public class CollectedArticlePreprocessor {

	/**
	 * 분석에 쓸 수 있는 최소 본문 길이.
	 */
	private static final int MIN_CONTENT_LENGTH = 200;

	/**
	 * 사건이 아니라 명단·정보라 분석 대상이 아닌 기사의 제목 접두 태그.
	 */
	private static final List<String> EXCLUDED_TITLE_PREFIXES =
			List.of("[인사]", "[부고]", "[동정]", "[신간]");

	/** 제목 어디에 있든 분석 대상이 아닌 문구. 넓게 잡으면 정상 기사가 걸리므로 구체적으로 둔다. */
	private static final List<String> EXCLUDED_TITLE_KEYWORDS =
			List.of("오늘의 운세", "띠별 운세");

	/** 본문에서 꺼낸 줄을 제목으로 볼 수 있는 최대 길이.  */
	private static final int MAX_TITLE_LENGTH = 120;

	/** 통신사 기사의 바이라인. */
	private static final Pattern BYLINE = Pattern.compile("(기자|특파원|통신원)\\s*=");

	/**
	 * <p>{@code ?} 나 {@code …} 로 끝나는 제목은 흔하므로 평서문 종결만 본다.
	 */
	private static final Pattern SENTENCE_END = Pattern.compile("[다요]\\.$");

	/** 본문 앞머리에 붙는 사이트 UI·분류 문구. 제목을 찾을 때 건너뛰고, 본문에서도 지운다. */
	private static final Set<String> LEADING_NOISE = Set.of(
			"AD", "기사 본문 영역", "AI 해설 기사", "크게보기", "기사 읽어주기", "세 줄 요약",
			"정치", "경제", "사회", "세계", "문화", "스포츠", "국제", "IT", "연예", "공유하기",
			"구글 검색 선호 출처로 추가",
			"읽어주기 기능은 크롬기반의", "브라우저에서만 사용하실 수 있습니다.");

	/**
	 * 본문 끝에 붙는 UI 문구. 한 줄이 통째로 이것일 때만 지운다.
	 */
	private static final Set<String> TRAILING_NOISE_LINES = Set.of(
			// KBS 반응 버튼
			"이 기사가 좋으셨다면", "좋아요", "응원해요", "후속 원해요", "이슈",
			// KBS 제보 안내
			"■ 제보하기", "▷ 카카오톡 : 'KBS제보' 검색, 채널 추가",
			"▷ 유튜브, 네이버, 다음에서도 KBS뉴스를 구독해주세요!",
			// YTN 제보 안내
			"※ '당신의 제보가 뉴스가 됩니다'", "[카카오톡] YTN 검색해 채널 추가",
			"[전화] 02-398-8585", "[메일] social@ytn.co.kr",
			// 이데일리 추천 위젯
			"실시간", "급상승 뉴스", "오늘의", "포토", "당신을 위한", "맞춤 뉴스by Dable",
			// 그 밖의 위젯·광고
			"관련기사", "Advertisement", "관심 있을 수도 있어요", "사진", "한 줄 정리",
			// 서울신문 AI 위젯
			"UNMASK ]", "기사 반응 MBTI 확인",
			"\"기사를 읽는 동안 깨어난 당신의 숨겨진 페르소나를 AI가 스캔합니다.\"",
			"기사를 끝까지 읽으셨나요? 이제 AI 퀴즈로 기사의 핵심 내용을 점검해보세요.");

	/** 줄이 통째로 같을 때 중복으로 볼 최소 길이. 짧은 줄은 대화체 기사에서 정상적으로 겹친다. */
	private static final int REPEATED_LINE_MIN_LENGTH = 40;

	/**
	 * 본문 끝에 붙는 저작권·UI 문구.
	 *
	 * <p>저작권 문구는 매체마다 표현이 전부 달라 목록으로는 끝이 없다. 실측에서만 스타뉴스·YTN·
	 * 세계일보·연합인포맥스·SBS·아주경제 등 십수 가지가 나왔다.
	 */
	private static final Pattern TRAILING_NOISE = Pattern.compile(
			"저작권|무단\\s*전재|재배포|Copyright|ⓒ|©|소셜 댓글|더보기|공유하기"
					+ "|실시간 뜨거운 관심|오늘의 숏뉴스|제보는|면책 조항|투자판단의 참고용|투자 참고용"
					+ "|위반 시 서비스 이용 제한|기사문의 및 제보|공감언론 뉴시스");

	/** 조회수·댓글 수처럼 숫자만 남은 줄. */
	private static final Pattern NUMBER_ONLY = Pattern.compile("\\d+");

	/**
	 * 정리 후 남아야 하는 최소 비율.
	 *
	 * <p>실측 2,000건에서 가장 많이 깎인 경우가 81% 였다. 절반 아래로 떨어지면 규칙이 본문을
	 * 잘못 먹은 것으로 보고 원본을 쓴다.
	 */
	private static final double MIN_KEPT_RATIO = 0.5;

	/**
	 * 저장할 기사만 남기고, 고칠 수 있는 것은 고친다.
	 *
	 * @return 분석에 쓸 수 있는 기사 목록
	 */
	public List<CollectedArticle> process(List<CollectedArticle> articles) {
		if (articles.isEmpty()) {
			return List.of();
		}

		// 제목 보정이 본문 정리보다 먼저다. 제목을 본문 앞머리에서 찾으므로 아직 원본이어야 한다.
		// 본문이 같은지는 정리를 마친 뒤에 본다. 군더더기만 다른 기사도 같은 것으로 잡힌다.
		List<CollectedArticle> kept = dropContentCollisions(articles.stream()
				.filter(this::isAnalyzable)
				.map(this::repairTitle)
				.map(this::cleanContent)
				.toList());

		int dropped = articles.size() - kept.size();
		if (dropped > 0) {
			log.info("전처리: {}건 중 {}건을 제외했습니다.", articles.size(), dropped);
		}
		return kept;
	}

	/**
	 * 제목이 언론사명으로만 온 기사의 제목을 본문에서 찾아 채운다.
	 * <p>찾지 못하면 원본을 그대로 둔다.
	 */
	private CollectedArticle repairTitle(CollectedArticle article) {
		if (!hasOutletNameAsTitle(article)) {
			return article;
		}

		String candidate = firstMeaningfulLine(article.content());
		if (!looksLikeTitle(candidate)) {
			log.info("제목을 본문에서 찾지 못해 원본을 유지합니다. ({}, {})",
					article.organizationName(), article.url());
			return article;
		}

		log.info("제목을 본문에서 보정했습니다. ({} -> {})", article.title(), candidate);
		return new CollectedArticle(candidate, article.url(), article.urlHash(),
				article.publishedAt(), article.content(), article.contentType(),
				article.sourceCategory(), article.organizationName(), article.organizationDomain());
	}

	/**
	 * 본문이 같은데 제목이 서로 다른 기사들을 통째로 버린다.

	 * <p><b>하나만 남기지 않고 전부 버린다.</b> 어느 제목이 그 본문의 주인인지 알 수 없어,
	 * 하나를 남기면 그 하나가 틀린 채로 남는다. (뉴스핌만 있어서 괜찮을듯)
	 *
	 * <p>제목까지 같으면 남긴다. 통신사 기사를 여러 매체가 받아쓴 것이라 정상이다. 실측에서
	 * 중복 33그룹(67건)이 여기 해당했다.
	 *
	 * <p>제목이 언론사명뿐인 기사는 판정에서 빼고, 제대로 된 제목이 하나로 모이면 그쪽만 남긴다.
	 */
	private List<CollectedArticle> dropContentCollisions(List<CollectedArticle> articles) {
		Map<String, List<CollectedArticle>> byContent = articles.stream()
				.collect(Collectors.groupingBy(
						article -> String.valueOf(article.content()),
						LinkedHashMap::new, Collectors.toList()));

		List<CollectedArticle> kept = new ArrayList<>();
		for (List<CollectedArticle> sameContent : byContent.values()) {
			List<CollectedArticle> candidates = titleKnown(sameContent);

			if (hasConflictingTitles(candidates)) {
				log.warn("본문이 같은데 제목이 달라 {}건을 제외합니다. ({})",
						sameContent.size(), sameContent.get(0).organizationName());
				sameContent.forEach(article -> log.info("  제외: {}", article.title()));
				continue;
			}
			if (candidates.size() < sameContent.size()) {
				log.info("본문이 같고 제목이 언론사명뿐이라 {}건을 제외합니다. (남긴 제목: {})",
						sameContent.size() - candidates.size(), candidates.get(0).title());
			}
			kept.addAll(candidates);
		}
		return kept;
	}

	/**
	 * 제목을 아는 기사만 남긴다. 전부 언론사명뿐이면 걸러낼 기준이 없어 그대로 돌려준다.
	 */
	private List<CollectedArticle> titleKnown(List<CollectedArticle> sameContent) {
		List<CollectedArticle> titled = sameContent.stream()
				.filter(article -> !hasOutletNameAsTitle(article))
				.toList();
		return titled.isEmpty() ? sameContent : titled;
	}

	private boolean hasConflictingTitles(List<CollectedArticle> sameContent) {
		return sameContent.stream().map(CollectedArticle::title).distinct().count() > 1;
	}

	/**
	 * 본문 앞뒤에 붙은 사이트 문구를 걷어낸다.
	 * <p>줄 단위로만 걷어낸다.
	 */
	private CollectedArticle cleanContent(CollectedArticle article) {
		String original = article.content();
		if (original == null || original.isBlank()) {
			return article;
		}

		List<String> deduplicated = dropRepeatedLines(original.lines().map(String::strip).toList());
		String body = String.join("\n", deduplicated);
		String cleaned = stripNoiseLines(deduplicated, article.title());

		if (cleaned.equals(original.strip())) {
			return article;
		}
		if (isOverTrimmed(body, cleaned)) {
			log.warn("본문이 지나치게 줄어 원본을 유지합니다. ({}자 -> {}자, {})",
					original.strip().length(), cleaned.length(), article.url());
			return article;
		}

		return new CollectedArticle(article.title(), article.url(), article.urlHash(),
				article.publishedAt(), cleaned, article.contentType(),
				article.sourceCategory(), article.organizationName(), article.organizationDomain());
	}

	private List<String> dropRepeatedLines(List<String> lines) {
		Set<String> seen = new HashSet<>();
		List<String> kept = new ArrayList<>();
		for (String line : lines) {
			if (line.length() >= REPEATED_LINE_MIN_LENGTH && !seen.add(line)) {
				continue;
			}
			kept.add(line);
		}
		return kept;
	}

	private String stripNoiseLines(List<String> lines, String title) {
		int start = 0;
		while (start < lines.size() && isLeadingNoise(lines.get(start))) {
			start++;
		}
		// 제목을 본문 앞머리에서 가져왔으면 그 줄은 본문에 남을 이유가 없다.
		if (start < lines.size() && title != null && lines.get(start).equals(title.strip())) {
			start++;
		}
		int end = lines.size();
		while (end > start && isTrailingNoise(lines.get(end - 1))) {
			end--;
		}

		return lines.subList(start, end).stream()
				.filter(line -> !line.isEmpty())
				.collect(Collectors.joining("\n"));
	}

	private boolean isLeadingNoise(String line) {
		return line.isEmpty() || LEADING_NOISE.contains(line);
	}

	private boolean isTrailingNoise(String line) {
		return line.isEmpty()
				|| NUMBER_ONLY.matcher(line).matches()
				|| TRAILING_NOISE_LINES.contains(line)
				|| TRAILING_NOISE.matcher(line).find();
	}

	/** 규칙이 본문까지 먹었는지. 실측에서 가장 많이 깎인 경우가 81% 였다. */
	private boolean isOverTrimmed(String original, String cleaned) {
		return cleaned.length() < original.strip().length() * MIN_KEPT_RATIO;
	}

	/**
	 * 제목이 언론사명과 같은지. 공백을 무시하고 본다.
	 */
	private boolean hasOutletNameAsTitle(CollectedArticle article) {
		if (article.title() == null || article.organizationName() == null) {
			return false;
		}
		return withoutWhitespace(article.title()).equals(withoutWhitespace(article.organizationName()));
	}

	private String withoutWhitespace(String value) {
		return value.replaceAll("\\s+", "");
	}

	/** 사이트 UI 문구를 건너뛴 첫 줄. 없으면 빈 문자열 */
	private String firstMeaningfulLine(String content) {
		if (content == null) {
			return "";
		}
		return content.lines()
				.map(String::strip)
				.filter(line -> !line.isEmpty() && !LEADING_NOISE.contains(line))
				.findFirst()
				.orElse("");
	}

	/** 제목으로 쓸 수 있는 줄인지. 길이·바이라인·문장 종결 셋을 모두 본다. */
	private boolean looksLikeTitle(String line) {
		return !line.isEmpty()
				&& line.length() <= MAX_TITLE_LENGTH
				&& !BYLINE.matcher(line).find()
				&& !SENTENCE_END.matcher(line).find();
	}

	private boolean isAnalyzable(CollectedArticle article) {
		if (hasTooLittleContent(article)) {
			log.info("본문이 짧아 제외합니다. ({}자, {})", contentLength(article), article.title());
			return false;
		}
		if (isNotNews(article.title())) {
			log.info("분석 대상이 아니라 제외합니다. ({})", article.title());
			return false;
		}
		return true;
	}

	private boolean hasTooLittleContent(CollectedArticle article) {
		return contentLength(article) < MIN_CONTENT_LENGTH;
	}

	private int contentLength(CollectedArticle article) {
		return article.content() == null ? 0 : article.content().strip().length();
	}

	/** 사건을 다루지 않는 기사인지. 인사·부고·운세처럼 명단이나 정보만 있는 것들이다. */
	private boolean isNotNews(String title) {
		if (title == null) {
			return false;
		}

		String normalized = title.strip().toLowerCase(Locale.KOREAN);
		return EXCLUDED_TITLE_PREFIXES.stream().anyMatch(normalized::startsWith)
				|| EXCLUDED_TITLE_KEYWORDS.stream().anyMatch(normalized::contains);
	}
}
