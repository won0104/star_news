package com.starlightnews.backend.domain.article.reconcile;

import com.starlightnews.backend.global.enums.AnalysisStatus;

/**
 * 대사에 쓰는 MySQL 기사 한 건의 상태.
 */
public record MysqlArticleState(long articleId, AnalysisStatus status, String nodeId) {
}
