package com.starlightnews.backend.domain.user.domain;

import java.time.Instant;

import com.starlightnews.backend.global.entity.BaseTimeEntity;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
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
	private Instant deletedAt;

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
}
