package com.starlightnews.backend.support;

import org.springframework.boot.test.autoconfigure.orm.jpa.TestEntityManager;

/**
 * FK 대상 행을 지정한 ID 로 미리 만들어 두는 테스트 픽스처.
 *
 * <p>테스트 DB 가 실제 MySQL 이라 마이그레이션의 외래키가 그대로 강제된다.
 * user_id·article_id 를 상수로 쓰는 테스트는 그 행이 실제로 있어야 한다.
 * (엔티티에서 스키마를 만들던 시절에는 외래키가 없어 아무 값이나 통과했다)
 */
public final class TestFixtures {

	/** 픽스처 기사들이 참조할 언론사 ID. 실제 데이터와 겹치지 않는 범위를 쓴다. */
	private static final long FIXTURE_ORGANIZATION_ID = 99_000L;

	private TestFixtures() {
	}

	/** 지정한 ID 로 사용자를 만든다. */
	public static void insertUsers(TestEntityManager entityManager, long... userIds) {
		for (long userId : userIds) {
			entityManager.getEntityManager()
					.createNativeQuery("INSERT INTO users (user_id, login_id, password_hash, nickname) "
							+ "VALUES (?1, ?2, 'hashed-password', ?3)")
					.setParameter(1, userId)
					.setParameter(2, "fixture-user-" + userId)
					.setParameter(3, "픽스처사용자" + userId)
					.executeUpdate();
		}
		entityManager.flush();
	}

	/** 지정한 ID 로 기사를 만든다. 기사가 참조할 언론사도 함께 만든다. */
	public static void insertArticles(TestEntityManager entityManager, long... articleIds) {
		entityManager.getEntityManager()
				.createNativeQuery("INSERT INTO news_organizations (organization_id, name, domain) "
						+ "VALUES (?1, '픽스처언론사', 'fixture.test') "
						+ "ON DUPLICATE KEY UPDATE organization_id = organization_id")
				.setParameter(1, FIXTURE_ORGANIZATION_ID)
				.executeUpdate();

		for (long articleId : articleIds) {
			entityManager.getEntityManager()
					.createNativeQuery("INSERT INTO articles "
							+ "(article_id, organization_id, title, url, url_hash, published_at, "
							+ " content, content_type, analysis_status) "
							+ "VALUES (?1, ?2, ?3, ?4, UNHEX(SHA2(?4, 256)), '2026-09-14 09:00:00', "
							+ " '픽스처 본문', 'FULL_TEXT', 'PROCESSING')")
					.setParameter(1, articleId)
					.setParameter(2, FIXTURE_ORGANIZATION_ID)
					.setParameter(3, "픽스처 기사 " + articleId)
					.setParameter(4, "https://fixture.test/articles/" + articleId)
					.executeUpdate();
		}
		entityManager.flush();
	}
}
