package com.starlightnews.backend.domain.recommendation.service;

import java.time.LocalDateTime;
import java.util.Collection;
import java.util.List;
import java.util.Map;
import java.util.function.Function;
import java.util.stream.Collectors;

import com.starlightnews.backend.domain.article.domain.Article;
import com.starlightnews.backend.domain.article.repository.ArticleRepository;
import com.starlightnews.backend.domain.recommendation.domain.RecommendationEvent;
import com.starlightnews.backend.domain.recommendation.repository.EventArticleRepository;
import com.starlightnews.backend.domain.recommendation.repository.RecommendationEventRepository;
import com.starlightnews.backend.domain.recommendation.repository.UserRecommendationRepository;
import com.starlightnews.backend.global.client.GmsClient;
import com.starlightnews.backend.global.error.BusinessException;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

/**
 * 추천 Event 의 요약을 만든다.
 *
 * <p>추천 배치가 회차를 저장한 직후에 돈다. 계산이 05:30·17:30, 공개가 06:00·18:00 이라 그 사이
 * 30분이 생성 창이다. 공개 시각에는 이미 채워져 있어야 조회가 요약을 기다리지 않는다.
 *
 * <p>요약은 Event 단위라 모든 사용자가 나눠 쓴다. 사용자가 늘어도 호출 수는 늘지 않는다.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class EventSummaryService {

	/** 요약에 넣을 기사 수. 관련도가 높은 순으로 고른다. */
	private static final int SOURCE_ARTICLE_LIMIT = 3;

	/** 기사 하나에서 넣을 최대 글자 수. 전문을 다 넣으면 호출 비용만 커진다. */
	private static final int SOURCE_CONTENT_LIMIT = 2_000;

	/**
	 * 기사를 압축하는 것이 아니라 사건의 맥락을 설명하게 한다.
	 *
	 * <p>이 요약은 사용자가 아직 접하지 않은 사건을 추천할 때 함께 보여 준다. 무슨 일이
	 * 있었는지만 적으면 그 사건을 모르는 사람에게는 여전히 낯설다. 어쩌다 그렇게 됐고 무엇이
	 * 걸려 있는지까지 있어야 읽을지 말지 판단할 수 있다.
	 *
	 * <p>다만 그 순서를 강제하지는 않는다. Topic 이 일곱이고 스포츠 경기 결과나 공연 소식처럼
	 * 배경과 파장이 아예 없는 사건이 있다. 빈 칸을 만들어 두면 모델이 채우려 들어 없는 말을
	 * 지어낸다. 무엇을 담을지는 기사에 있는 것에 맡기고, 여기서는 목적만 준다.
	 */
	private static final String INSTRUCTION = """
			너는 뉴스 사건을 설명하는 편집자다. 주어진 기사들은 모두 같은 사건을 다룬다.
			이 사건을 처음 접하는 독자가 맥락까지 이해하도록 한국어로 설명하라.

			- 3문장 이내, 전체 300자 이내로 쓴다.
			- 이 사건을 처음 보는 독자가 "왜 이게 뉴스인지" 알 수 있게 쓴다.
			- 기사에 배경이나 파장이 나와 있으면 함께 담고, 나와 있지 않으면 사건 자체만 쓴다.
			  빈 곳을 채우려고 추측하지 않는다.
			- 이 사건에 직접 관련된 내용만 쓴다. 기사에 딸려 나온 다른 회사·제품·통계는 넣지 않는다.
			- 사건을 나열하지 말고 인과로 잇는다.
			- 언론사 이름, 기자 이름, 기사 제목은 언급하지 않는다.
			- "이 기사는", "요약하면" 같은 말로 시작하지 않고 사건 내용부터 바로 쓴다.""";

	private final RecommendationEventRepository eventRepository;
	private final EventArticleRepository eventArticleRepository;
	private final ArticleRepository articleRepository;
	private final UserRecommendationRepository userRecommendationRepository;
	private final EventSummaryWriter writer;
	private final GmsClient gmsClient;

	/**
	 * 한 회차에 추천된 Event 중 요약이 필요한 것만 만든다.
	 *
	 * <p>한 건이 실패해도 나머지는 계속한다. 요약이 없어도 추천은 보여야 하고, 실패한 Event 는
	 * 다음 회차에 다시 대상으로 잡힌다.
	 *
	 * @param availableAt 회차의 공개 시각
	 * @return 새로 만든 요약 수
	 */
	public int generateForCycle(LocalDateTime availableAt) {
		return generateFor(userRecommendationRepository.findEventIdsByAvailableAt(availableAt));
	}

	/** @return 새로 만든 요약 수 */
	int generateFor(Collection<String> recommendedEventIds) {
		if (recommendedEventIds.isEmpty()) {
			return 0;
		}

		List<String> targets = eventRepository.findEventIdsNeedingSummary(recommendedEventIds);
		if (targets.isEmpty()) {
			log.info("Event 요약: 새로 만들 것이 없습니다. (추천 Event {}개)", recommendedEventIds.size());
			return 0;
		}

		int generated = 0;
		for (String eventId : targets) {
			if (generateOne(eventId)) {
				generated++;
			}
		}

		log.info("Event 요약: 대상 {}개 중 {}개 생성", targets.size(), generated);
		return generated;
	}

	/** @return 요약을 만들어 저장했으면 true */
	private boolean generateOne(String eventId) {
		try {
			RecommendationEvent event = eventRepository.findById(eventId).orElse(null);
			if (event == null) {
				return false;
			}

			String sources = sourceText(eventId);
			if (sources.isBlank()) {
				// 기사가 아직 그래프에 붙지 않았다. 다음 회차에 다시 대상으로 잡힌다.
				log.info("Event 요약 건너뜀: 근거 기사가 없습니다. ({})", event.getTitle());
				return false;
			}

			writer.markProcessing(eventId);
			String summary = gmsClient.generate(INSTRUCTION,
					"사건 이름: %s%n%n%s".formatted(event.getTitle(), sources));
			writer.saveSummary(eventId, summary);
			return true;
		} catch (BusinessException generationFailure) {
			// 요약이 없어도 추천은 보여야 한다. 회차를 통째로 실패시키지 않는다.
			log.warn("Event 요약 실패 ({}, code={})", eventId, generationFailure.getErrorCode().getCode());
			writer.markFailed(eventId);
			return false;
		}
	}

	/** 관련도 높은 기사 몇 개를 모델에 넣을 형태로 붙인다. */
	private String sourceText(String eventId) {
		List<Long> articleIds = eventArticleRepository.findArticleIdsByEvent(eventId).stream()
				.limit(SOURCE_ARTICLE_LIMIT)
				.toList();
		if (articleIds.isEmpty()) {
			return "";
		}

		Map<Long, Article> articles = articleRepository
				.findAllWithOrganizationByArticleIdIn(articleIds).stream()
				.collect(Collectors.toMap(Article::getArticleId, Function.identity()));

		return articleIds.stream()
				.map(articles::get)
				.filter(article -> article != null)
				.map(article -> "%s%n%s".formatted(article.getTitle(), truncate(article.getContent())))
				.collect(Collectors.joining("\n\n"));
	}

	private String truncate(String content) {
		if (content == null) {
			return "";
		}
		return content.length() <= SOURCE_CONTENT_LIMIT
				? content : content.substring(0, SOURCE_CONTENT_LIMIT);
	}
}
