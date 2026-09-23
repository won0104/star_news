package com.starlightnews.backend.global.security;

import java.util.Objects;

/** Refresh Token 교체 결과. ROTATED 일 때만 userId가 있다. */
public record RefreshSessionRotationResult(
		Status status,
		Long userId
) {

	public enum Status {
		ROTATED,
		NOT_FOUND,
		REUSED
	}

	public RefreshSessionRotationResult {
		Objects.requireNonNull(status, "status must not be null");
		if ((status == Status.ROTATED) != (userId != null)) {
			throw new IllegalArgumentException("userId must exist only for ROTATED");
		}
	}

	public static RefreshSessionRotationResult rotated(long userId) {
		return new RefreshSessionRotationResult(Status.ROTATED, userId);
	}

	public static RefreshSessionRotationResult notFound() {
		return new RefreshSessionRotationResult(Status.NOT_FOUND, null);
	}

	public static RefreshSessionRotationResult reused() {
		return new RefreshSessionRotationResult(Status.REUSED, null);
	}
}
