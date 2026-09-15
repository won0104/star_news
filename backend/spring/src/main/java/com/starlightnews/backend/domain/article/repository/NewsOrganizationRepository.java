package com.starlightnews.backend.domain.article.repository;

import java.util.Optional;

import com.starlightnews.backend.domain.article.domain.NewsOrganization;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.Repository;
import org.springframework.data.repository.query.Param;

/**
 * 언론사 조회·저장. (news_organizations)
 */
public interface NewsOrganizationRepository extends Repository<NewsOrganization, Long> {

	Optional<NewsOrganization> findById(Long id);

	/** 도메인으로 언론사 ID 를 찾는다. 식별 키라 저장 전에 이걸 먼저 본다. */
	@Query("SELECT o.id FROM NewsOrganization o WHERE o.domain = :domain")
	Optional<Long> findIdByDomain(@Param("domain") String domain);

	/** 이름으로 언론사 ID 를 찾는다. 도메인이 없는 기사와 name 충돌 복구에 쓴다. */
	@Query("SELECT o.id FROM NewsOrganization o WHERE o.name = :name")
	Optional<Long> findIdByName(@Param("name") String name);

	/**
	 * 언론사를 한 문장으로 만든다. 이미 있으면(name 또는 domain UNIQUE 충돌) 아무것도 바꾸지 않는다.
	 *
	 * <p>조회 후 INSERT 사이에 다른 수집 스레드가 같은 언론사를 만들 수 있다. 제약 위반을 예외로
	 * 받아 되돌리는 방식은 위반이 commit 시점에 나서 잡히지 않고, UPDATE 를 먼저 치면 InnoDB 갭 락으로
	 * 데드락이 난다. 단일 Upsert 문장이 두 문제를 모두 피한다.
	 *
	 * <p>영향 행 수는 돌려주지 않는다. 삽입됐는지 무시됐는지를 나타내는 값이 MySQL 과 H2 에서 다르게
	 * 나오므로, 호출 측은 결과를 다시 조회해 확인한다.
	 */
	@Modifying
	@Query(value = "INSERT INTO news_organizations (name, domain) VALUES (:name, :domain) "
			+ "ON DUPLICATE KEY UPDATE organization_id = organization_id",
			nativeQuery = true)
	void insertIfAbsent(@Param("name") String name, @Param("domain") String domain);
}
