package com.starlightnews.backend.domain.user.domain;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Objects;

import com.starlightnews.backend.global.entity.BaseTimeEntity;
import com.starlightnews.backend.global.enums.InterestType;
import com.starlightnews.backend.global.enums.TopicCode;
import jakarta.persistence.CascadeType;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.OneToMany;
import jakarta.persistence.Table;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Entity
@Table(name = "users")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class User extends BaseTimeEntity {

	@Id
	@GeneratedValue(strategy = GenerationType.IDENTITY)
	@Column(name = "user_id")
	private Long id;

	@Column(name = "login_id", nullable = false, unique = true, length = 50)
	private String loginId;

	@Column(name = "password_hash", nullable = false, length = 255)
	private String passwordHash;

	@Column(nullable = false, length = 50)
	private String nickname;

	@Column(name = "deleted_at")
	private LocalDateTime deletedAt;

	@OneToMany(mappedBy = "user", cascade = CascadeType.ALL, orphanRemoval = true)
	private List<UserInterest> interests = new ArrayList<>();

	private User(String loginId, String passwordHash, String nickname) {
		this.loginId = loginId;
		this.passwordHash = passwordHash;
		this.nickname = nickname;
	}

	/**
	 * 회원가입 시 신규 사용자를 생성한다. 비밀번호는 이미 단방향 암호화된 해시를 전달받는다.
	 */
	public static User create(String loginId, String passwordHash, String nickname) {
		return new User(loginId, passwordHash, nickname);
	}

	public boolean isDeleted() {
		return deletedAt != null;
	}

	/**
	 * 회원 탈퇴. 실제 행을 지우지 않고 탈퇴 시각만 기록한다(soft delete).
	 */
	public void markDeleted() {
		this.deletedAt = LocalDateTime.now();
	}

	/**
	 * 관심(INTEREST) 또는 비관심(DISLIKE) 분야를 추가한다. 저장은 User 저장 시 cascade 로 함께 처리된다.
	 */
	public void addInterest(TopicCode topicCode, InterestType interestType) {
		interests.add(UserInterest.of(this, topicCode, interestType));
	}

	/**
	 * 지정한 관심 유형의 Topic 코드를 공통 Enum 선언 순서로 반환한다.
	 */
	public List<TopicCode> getTopicCodes(InterestType interestType) {
		Objects.requireNonNull(interestType, "interestType must not be null");
		return interests.stream()
				.filter(interest -> interest.hasType(interestType))
				.map(UserInterest::getTopicCode)
				.sorted()
				.toList();
	}
}
