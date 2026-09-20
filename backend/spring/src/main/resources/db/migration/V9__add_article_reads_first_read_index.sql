-- 최근 12주 최초 열람 통계를 사용자별로 조회할 때 사용하는 인덱스다.
CREATE INDEX `idx_article_reads_user_first_read`
    ON `article_reads` (`user_id`, `first_read_at` DESC);
