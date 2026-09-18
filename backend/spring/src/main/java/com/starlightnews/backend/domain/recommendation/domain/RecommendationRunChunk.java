package com.starlightnews.backend.domain.recommendation.domain;

import java.util.List;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

/**
 * 회차 안 사용자 묶음 하나의 결과. ({@code recommendation_run_chunks})
 *
 * <p>묶음에 담았던 사용자 목록을 그대로 남긴다. 실패한 묶음을 다시 보낼 때 페이지를 다시 읽으면
 * 그 사이 가입·탈퇴로 경계가 밀려 다른 사용자가 섞인다.
 */
@Entity
@Table(name = "recommendation_run_chunks")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class RecommendationRunChunk {

	@Id
	@GeneratedValue(strategy = GenerationType.IDENTITY)
	@Column(name = "chunk_id")
	private Long chunkId;

	@Column(name = "run_id", nullable = false)
	private Long runId;

	/** 회차 안에서 몇 번째 묶음인지. 0부터 센다. */
	@Column(name = "chunk_no", nullable = false)
	private int chunkNo;

	@JdbcTypeCode(SqlTypes.JSON)
	@Column(name = "user_ids", nullable = false)
	private List<Long> userIds;

	@Column(name = "user_count", nullable = false)
	private int userCount;

	@Enumerated(EnumType.STRING)
	@Column(name = "status", nullable = false, length = 16)
	private RecommendationRunChunkStatus status;

	@Column(name = "attempts", nullable = false)
	private int attempts;

	/** 마지막 실패 원인. 내부 API 오류 코드이거나 저장 실패다. 성공하면 비운다. */
	@Column(name = "failure_code", length = 64)
	private String failureCode;

	private RecommendationRunChunk(Long runId, int chunkNo, List<Long> userIds,
			RecommendationRunChunkStatus status, String failureCode) {
		this.runId = runId;
		this.chunkNo = chunkNo;
		this.userIds = List.copyOf(userIds);
		this.userCount = userIds.size();
		this.status = status;
		this.attempts = 1;
		this.failureCode = failureCode;
	}

	public static RecommendationRunChunk succeeded(Long runId, int chunkNo, List<Long> userIds) {
		return new RecommendationRunChunk(runId, chunkNo, userIds, RecommendationRunChunkStatus.SUCCEEDED, null);
	}

	public static RecommendationRunChunk failed(Long runId, int chunkNo, List<Long> userIds, String failureCode) {
		return new RecommendationRunChunk(runId, chunkNo, userIds, RecommendationRunChunkStatus.FAILED,
				failureCode);
	}

	/** 다시 보내 성공했다. */
	public void retrySucceeded() {
		this.attempts++;
		this.status = RecommendationRunChunkStatus.SUCCEEDED;
		this.failureCode = null;
	}

	/** 다시 보냈지만 또 실패했다. 원인은 마지막 것으로 바꾼다. */
	public void retryFailed(String failureCode) {
		this.attempts++;
		this.status = RecommendationRunChunkStatus.FAILED;
		this.failureCode = failureCode;
	}
}
