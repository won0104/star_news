package com.starlightnews.backend.domain.article.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;

/**
 * 정규화된 언론사. (news_organizations)
 * 관련 기사 응답의 organizationName 용 읽기 부분 매핑.
 */
@Entity
@Table(name = "news_organizations")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class NewsOrganization {

	@Id
	@GeneratedValue(strategy = GenerationType.IDENTITY)
	@Column(name = "organization_id")
	private Long id;

	@Column(nullable = false, length = 150)
	private String name;

	public NewsOrganization(String name) {
		this.name = name;
	}
}
