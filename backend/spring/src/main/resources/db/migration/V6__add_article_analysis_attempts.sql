-- 기사 AI 분석의 일시 실패 횟수.
-- 한도(app.article.analysis.max-attempts)에 닿으면 FAILED 로 두고 더 부르지 않는다.
-- 세지 않으면 분석이 계속 실패하는 기사 하나가 회차마다 AI 추론 시간을 태운다.
ALTER TABLE `articles`
    ADD COLUMN `analysis_attempts` INT NOT NULL DEFAULT 0 AFTER `analysis_status`;

-- 분석 대기열 조회용. 회차마다 PROCESSING 이고 시도 횟수가 한도 아래인 기사를 오래된 순으로 고른다.
CREATE INDEX `idx_articles_analysis_queue`
    ON `articles` (`analysis_status`, `analysis_attempts`, `article_id`);
