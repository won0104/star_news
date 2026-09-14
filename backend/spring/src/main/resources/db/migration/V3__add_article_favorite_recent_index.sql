CREATE INDEX `idx_user_article_favorites_user_recent`
    ON `user_article_favorites` (`user_id`, `favorited_at` DESC, `article_id` DESC);
