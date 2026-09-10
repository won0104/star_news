package com.starlightnews.backend.domain.graph.support;

import java.nio.charset.StandardCharsets;
import java.util.Base64;

import com.starlightnews.backend.domain.graph.exception.GraphErrorCode;
import com.starlightnews.backend.global.error.BusinessException;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.catchThrowable;

class NeighborCursorTest {

	private static final String NODE_KEY = "00000024-0920-4000-8000-000000000001";

	private static String base64(String raw) {
		return Base64.getUrlEncoder().withoutPadding().encodeToString(raw.getBytes(StandardCharsets.UTF_8));
	}

	private GraphErrorCode errorCodeOf(Throwable throwable) {
		assertThat(throwable).isInstanceOf(BusinessException.class);
		return (GraphErrorCode) ((BusinessException) throwable).getErrorCode();
	}

	@Test
	void 인코딩한_커서를_디코딩하면_원래_값이_복원된다() {
		NeighborCursor original = new NeighborCursor(0.91, "ENTITY", NODE_KEY);

		NeighborCursor restored = NeighborCursor.decode(original.encode());

		assertThat(restored).isEqualTo(original);
	}

	@Test
	void 인코딩_결과는_원시_값을_그대로_노출하지_않는다() {
		String encoded = new NeighborCursor(0.91, "ENTITY", NODE_KEY).encode();

		assertThat(encoded).doesNotContain("|", " ", "ENTITY", NODE_KEY);
	}

	@Test
	void base64가_아니면_INVALID_CURSOR() {
		Throwable thrown = catchThrowable(() -> NeighborCursor.decode("!!! not base64 !!!"));

		assertThat(errorCodeOf(thrown)).isEqualTo(GraphErrorCode.INVALID_CURSOR);
	}

	@Test
	void 필드_수가_부족하면_INVALID_CURSOR() {
		Throwable thrown = catchThrowable(() -> NeighborCursor.decode(base64("0.91" + "|" + "ENTITY")));

		assertThat(errorCodeOf(thrown)).isEqualTo(GraphErrorCode.INVALID_CURSOR);
	}

	@Test
	void neighborScore가_숫자가_아니면_INVALID_CURSOR() {
		Throwable thrown = catchThrowable(
				() -> NeighborCursor.decode(base64("not-a-number|ENTITY|" + NODE_KEY)));

		assertThat(errorCodeOf(thrown)).isEqualTo(GraphErrorCode.INVALID_CURSOR);
	}
}
