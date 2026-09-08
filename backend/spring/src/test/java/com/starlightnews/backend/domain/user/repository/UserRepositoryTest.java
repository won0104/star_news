package com.starlightnews.backend.domain.user.repository;

import java.util.Optional;

import com.starlightnews.backend.domain.user.domain.User;
import com.starlightnews.backend.domain.user.domain.UserInterest;
import com.starlightnews.backend.global.config.JpaConfig;
import com.starlightnews.backend.global.enums.InterestType;
import com.starlightnews.backend.global.enums.TopicCode;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.jdbc.AutoConfigureTestDatabase;
import org.springframework.boot.test.autoconfigure.orm.jpa.DataJpaTest;
import org.springframework.boot.test.autoconfigure.orm.jpa.TestEntityManager;
import org.springframework.context.annotation.Import;
import org.springframework.test.context.ActiveProfiles;

import org.springframework.dao.DataIntegrityViolationException;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.assertj.core.api.Assertions.tuple;

@DataJpaTest
@Import(JpaConfig.class)
@ActiveProfiles("test")
@AutoConfigureTestDatabase(replace = AutoConfigureTestDatabase.Replace.NONE)
class UserRepositoryTest {

	@Autowired
	private UserRepository userRepository;

	@Autowired
	private TestEntityManager entityManager;

	@Test
	void loginId로_사용자_존재_여부를_확인한다() {
		userRepository.save(User.create("starlight01", "hashed-password", "별빛"));
		entityManager.flush();
		entityManager.clear();

		assertThat(userRepository.existsByLoginId("starlight01")).isTrue();
		assertThat(userRepository.existsByLoginId("nobody")).isFalse();
	}

	@Test
	void loginId로_사용자를_조회한다() {
		userRepository.save(User.create("starlight01", "hashed-password", "별빛"));
		entityManager.flush();
		entityManager.clear();

		Optional<User> found = userRepository.findByLoginId("starlight01");

		assertThat(found).isPresent();
		assertThat(found.get().getLoginId()).isEqualTo("starlight01");
		assertThat(found.get().getPasswordHash()).isEqualTo("hashed-password");
		assertThat(found.get().getNickname()).isEqualTo("별빛");
	}

	@Test
	void 존재하지_않는_loginId_조회시_빈_Optional을_반환한다() {
		assertThat(userRepository.findByLoginId("nobody")).isEmpty();
	}

	@Test
	void 저장하면_생성일시와_수정일시가_자동으로_채워진다() {
		User saved = userRepository.save(User.create("starlight01", "hashed-password", "별빛"));
		entityManager.flush();

		assertThat(saved.getCreatedAt()).isNotNull();
		assertThat(saved.getUpdatedAt()).isNotNull();
	}

	@Test
	void 신규_사용자는_deletedAt이_null이다() {
		User saved = userRepository.save(User.create("starlight01", "hashed-password", "별빛"));
		entityManager.flush();

		assertThat(saved.getDeletedAt()).isNull();
	}

	@Test
	void loginId는_유일해야_한다() {
		userRepository.saveAndFlush(User.create("starlight01", "hashed-password", "별빛"));
		entityManager.clear();

		assertThatThrownBy(() ->
				userRepository.saveAndFlush(User.create("starlight01", "another-hash", "다른별빛")))
				.isInstanceOf(DataIntegrityViolationException.class);
	}

	@Test
	void 사용자를_저장하면_담아둔_관심분야도_함께_저장된다() {
		User user = User.create("starlight01", "hashed-password", "별빛");
		user.addInterest(TopicCode.ECONOMY, InterestType.INTEREST);
		user.addInterest(TopicCode.IT_SCIENCE, InterestType.INTEREST);
		user.addInterest(TopicCode.SPORTS, InterestType.DISLIKE);

		userRepository.save(user);
		entityManager.flush();
		entityManager.clear();

		User found = userRepository.findByLoginId("starlight01").orElseThrow();

		assertThat(found.getInterests()).hasSize(3);
		assertThat(found.getInterests())
				.extracting(interest -> interest.getId().getTopicCode(), UserInterest::getInterestType)
				.containsExactlyInAnyOrder(
						tuple(TopicCode.ECONOMY, InterestType.INTEREST),
						tuple(TopicCode.IT_SCIENCE, InterestType.INTEREST),
						tuple(TopicCode.SPORTS, InterestType.DISLIKE)
				);
	}

	@Test
	void 저장된_관심분야의_복합키는_사용자ID와_토픽코드로_구성된다() {
		User user = User.create("starlight01", "hashed-password", "별빛");
		user.addInterest(TopicCode.ECONOMY, InterestType.INTEREST);

		User saved = userRepository.save(user);
		entityManager.flush();
		entityManager.clear();

		UserInterest interest = userRepository.findByLoginId("starlight01").orElseThrow()
				.getInterests().get(0);

		assertThat(interest.getId().getUserId()).isEqualTo(saved.getId());
		assertThat(interest.getId().getTopicCode()).isEqualTo(TopicCode.ECONOMY);
	}

	@Test
	void 관심분야를_담지_않으면_빈_리스트다() {
		userRepository.save(User.create("starlight01", "hashed-password", "별빛"));
		entityManager.flush();
		entityManager.clear();

		User found = userRepository.findByLoginId("starlight01").orElseThrow();

		assertThat(found.getInterests()).isEmpty();
	}

	@Test
	void 사용자를_삭제하면_관심분야도_함께_삭제된다() {
		User user = User.create("starlight01", "hashed-password", "별빛");
		user.addInterest(TopicCode.ECONOMY, InterestType.INTEREST);
		Long userId = userRepository.saveAndFlush(user).getId();
		entityManager.clear();

		userRepository.deleteById(userId);
		entityManager.flush();

		Long interestCount = entityManager.getEntityManager()
				.createQuery("select count(i) from UserInterest i", Long.class)
				.getSingleResult();
		assertThat(interestCount).isZero();
	}
}
