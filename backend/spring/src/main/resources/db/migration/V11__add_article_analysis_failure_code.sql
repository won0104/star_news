-- 기사별 마지막 분석 실패 원인.
-- 지금은 실패가 로그에만 남아, FAILED 로 굳은 기사를 보고 원인을 알 수 없다. 제한 시간을 넘겨
-- 실패한 기사와 AI 가 내용을 못 뽑아 실패한 기사는 대응이 다르다. 앞엣것만 다시 돌리면 된다.
ALTER TABLE `articles`
    ADD COLUMN `analysis_failure_code` VARCHAR(64) NULL AFTER `analysis_attempts`;
