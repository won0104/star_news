package com.starlightnews.backend.global.response;

import java.util.ArrayList;
import java.util.List;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

class CursorResponseTest {

	@Test
	void copiesItemsToPreventExternalModification() {
		List<String> items = new ArrayList<>(List.of("first"));

		CursorResponse<String> response = CursorResponse.of(items, true, "next-cursor");
		items.add("second");

		assertEquals(List.of("first"), response.items());
		assertThrows(UnsupportedOperationException.class, () -> response.items().add("third"));
	}

	@Test
	void convertsNullItemsToEmptyList() {
		CursorResponse<String> response = CursorResponse.of(null, false, null);

		assertEquals(List.of(), response.items());
	}
}
