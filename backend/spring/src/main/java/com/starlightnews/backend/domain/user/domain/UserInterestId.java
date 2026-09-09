package com.starlightnews.backend.domain.user.domain;

import java.io.Serializable;

import com.starlightnews.backend.global.enums.TopicCode;
import jakarta.persistence.Column;
import jakarta.persistence.Embeddable;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import lombok.AccessLevel;
import lombok.EqualsAndHashCode;
import lombok.Getter;
import lombok.NoArgsConstructor;

/**
 * user_interest 테이블의 복합 기본키 (user_id, topic_code).
 * userId 는 @MapsId 를 통해 연관된 User 로부터 채워지므로 불변 record 로 만들지 않는다.
 */
@Embeddable
@Getter
@EqualsAndHashCode
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class UserInterestId implements Serializable {

	@Column(name = "user_id")
	private Long userId;

	@Enumerated(EnumType.STRING)
	@Column(name = "topic_code", length = 32)
	private TopicCode topicCode;

	UserInterestId(TopicCode topicCode) {
		this.topicCode = topicCode;
	}
}
