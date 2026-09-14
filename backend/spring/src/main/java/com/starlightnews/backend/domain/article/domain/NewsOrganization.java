package com.starlightnews.backend.domain.article.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import jakarta.persistence.UniqueConstraint;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;

/**
 * 정규화된 언론사. (news_organizations)
 *
 * <p>식별 키는 domain 이고 name 은 표시용이다. 제공처가 언론사명을 도메인 문자열로 주는 경우가 있어
 * 이름을 그대로 믿을 수 없다. 도메인으로 묶어두면 표시명이 잘못 들어와도 나중에 name 만 UPDATE 하면 되고,
 * articles.organization_id 를 다시 지정할 필요가 없다.
 */
@Entity
@Table(name = "news_organizations", uniqueConstraints = {
		// 실제 스키마(V1 마이그레이션)의 제약을 엔티티에도 선언한다.
		// H2 테스트 DB 는 엔티티에서 스키마를 만들기 때문에, 여기 없으면 중복이 그냥 들어가
		// Upsert 동작을 검증할 수 없다.
		@UniqueConstraint(name = "uk_news_organizations_name", columnNames = "name"),
		@UniqueConstraint(name = "uk_news_organizations_domain", columnNames = "domain")
})
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class NewsOrganization {

	@Id
	@GeneratedValue(strategy = GenerationType.IDENTITY)
	@Column(name = "organization_id")
	private Long id;

	@Column(nullable = false, length = 150)
	private String name;

	/** 언론사 홈 도메인. 제공처가 주지 않으면 null 이고, 그때는 name 으로 식별한다. */
	@Column(length = 255)
	private String domain;

	public NewsOrganization(String name) {
		this(name, null);
	}

	public NewsOrganization(String name, String domain) {
		this.name = name;
		this.domain = domain;
	}
}
