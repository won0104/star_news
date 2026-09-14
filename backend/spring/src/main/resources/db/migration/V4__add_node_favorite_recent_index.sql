CREATE INDEX `idx_user_node_favorites_user_recent`
    ON `user_node_favorites` (`user_id`, `favorited_at` DESC, `node_type` ASC, `node_id` ASC);
