package com.starlightnews.backend.domain.recommendation.service;

import java.time.LocalDateTime;

import com.starlightnews.backend.domain.recommendation.repository.RecommendationEventRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

/**
 * Event 요약 결과를 Event 하나씩 따로 커밋한다.
 *
 * <p>요약 생성은 GMS 호출이라 오래 걸리고 중간에 실패한다. 한 트랜잭션으로 묶으면 마지막 한 건이
 * 실패했을 때 앞서 만든 요약까지 되돌아가고, 트랜잭션이 GMS 응답을 기다리는 동안 열려 있게 된다.
 *
 * <p>쓰기를 별도 빈으로 뺀 이유는 자기 호출로는 {@code @Transactional} 프록시를 타지 못해서다.
 */
@Component
@RequiredArgsConstructor
public class EventSummaryWriter {

	private final RecommendationEventRepository eventRepository;

	@Transactional
	public void markProcessing(String eventId) {
		eventRepository.markSummaryProcessing(eventId);
	}

	@Transactional
	public void saveSummary(String eventId, String summary) {
		eventRepository.saveSummary(eventId, summary, LocalDateTime.now());
	}

	@Transactional
	public void markFailed(String eventId) {
		eventRepository.markSummaryFailed(eventId);
	}
}
