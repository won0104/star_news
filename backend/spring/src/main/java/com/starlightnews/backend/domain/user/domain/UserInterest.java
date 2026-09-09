package com.starlightnews.backend.domain.user.domain;

import com.starlightnews.backend.global.entity.BaseTimeEntity;
import com.starlightnews.backend.global.enums.InterestType;
import com.starlightnews.backend.global.enums.TopicCode;
import jakarta.persistence.Column;
import jakarta.persistence.EmbeddedId;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.FetchType;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.MapsId;
import jakarta.persistence.Table;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Entity
@Table(name = "user_interest")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class UserInterest extends BaseTimeEntity {

	@EmbeddedId
	private UserInterestId id;

	@MapsId("userId")
	@ManyToOne(fetch = FetchType.LAZY, optional = false)
	@JoinColumn(name = "user_id")
	private User user;

	@Enumerated(EnumType.STRING)
	@Column(name = "interest_type", nullable = false, length = 20)
	private InterestType interestType;

	private UserInterest(User user, TopicCode topicCode, InterestType interestType) {
		this.user = user;
		this.id = new UserInterestId(topicCode);
		this.interestType = interestType;
	}

	/**
	 * User 를 통해서만 생성한다. (User.addInterest)
	 */
	static UserInterest of(User user, TopicCode topicCode, InterestType interestType) {
		return new UserInterest(user, topicCode, interestType);
	}
}
