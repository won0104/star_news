package com.starlightnews.backend.domain.article.repository;

import com.starlightnews.backend.domain.article.domain.NewsOrganization;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.jdbc.AutoConfigureTestDatabase;
import org.springframework.boot.test.autoconfigure.orm.jpa.DataJpaTest;
import org.springframework.boot.test.autoconfigure.orm.jpa.TestEntityManager;
import org.springframework.test.context.ActiveProfiles;

import static org.assertj.core.api.Assertions.assertThat;

@DataJpaTest
@ActiveProfiles("test")
@AutoConfigureTestDatabase(replace = AutoConfigureTestDatabase.Replace.NONE)
class NewsOrganizationRepositoryTest {

	@Autowired
	private NewsOrganizationRepository newsOrganizationRepository;

	@Autowired
	private TestEntityManager entityManager;

	@Test
	void insertIfAbsent는_없으면_이름과_도메인으로_새로_만든다() {
		newsOrganizationRepository.insertIfAbsent("연합뉴스", "www.yna.co.kr");
		entityManager.clear();

		Long id = newsOrganizationRepository.findIdByDomain("www.yna.co.kr").orElseThrow();
		NewsOrganization found = newsOrganizationRepository.findById(id).orElseThrow();
		assertThat(found.getName()).isEqualTo("연합뉴스");
		assertThat(found.getDomain()).isEqualTo("www.yna.co.kr");
	}

	@Test
	void insertIfAbsent는_같은_도메인이_이미_있으면_아무것도_바꾸지_않는다() {
		entityManager.persist(new NewsOrganization("연합뉴스", "www.yna.co.kr"));
		entityManager.flush();

		newsOrganizationRepository.insertIfAbsent("다른 이름", "www.yna.co.kr");
		entityManager.clear();

		Long id = newsOrganizationRepository.findIdByDomain("www.yna.co.kr").orElseThrow();
		// 표시명을 덮어쓰지 않는다. 이름 정리는 운영에서 UPDATE 로 한다.
		assertThat(newsOrganizationRepository.findById(id).orElseThrow().getName())
				.isEqualTo("연합뉴스");
	}

	@Test
	void insertIfAbsent는_같은_이름이_다른_도메인으로_있어도_새로_만들지_않는다() {
		// name 에도 UNIQUE 가 걸려 있어 INSERT 가 무시된다. 호출 측이 이름으로 찾아 복구한다.
		entityManager.persist(new NewsOrganization("연합뉴스", "www.yna.co.kr"));
		entityManager.flush();

		newsOrganizationRepository.insertIfAbsent("연합뉴스", "m.yna.co.kr");
		entityManager.clear();

		assertThat(newsOrganizationRepository.findIdByDomain("m.yna.co.kr")).isEmpty();
		assertThat(newsOrganizationRepository.findIdByName("연합뉴스")).isPresent();
	}

	@Test
	void 도메인이_없는_언론사도_저장된다() {
		newsOrganizationRepository.insertIfAbsent("이름만 있는 매체", null);
		entityManager.clear();

		Long id = newsOrganizationRepository.findIdByName("이름만 있는 매체").orElseThrow();
		assertThat(newsOrganizationRepository.findById(id).orElseThrow().getDomain()).isNull();
	}

	@Test
	void 도메인이_null인_언론사가_여러_개여도_충돌하지_않는다() {
		// MySQL 과 H2 모두 UNIQUE 컬럼의 NULL 은 중복으로 보지 않는다.
		newsOrganizationRepository.insertIfAbsent("매체 A", null);
		newsOrganizationRepository.insertIfAbsent("매체 B", null);
		entityManager.clear();

		assertThat(newsOrganizationRepository.findIdByName("매체 A")).isPresent();
		assertThat(newsOrganizationRepository.findIdByName("매체 B")).isPresent();
	}

	@Test
	void findIdByDomain은_없는_도메인이면_빈_Optional이다() {
		assertThat(newsOrganizationRepository.findIdByDomain("없는.도메인")).isEmpty();
	}
}
