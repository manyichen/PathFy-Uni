-- 人岗匹配快照：用于报告页优先复用最近一次匹配结果

CREATE TABLE IF NOT EXISTS match_runs (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id BIGINT UNSIGNED NOT NULL,
  resume_id BIGINT UNSIGNED NOT NULL,
  match_goal VARCHAR(16) NOT NULL DEFAULT 'fit',
  q VARCHAR(191) NULL,
  location_q VARCHAR(191) NULL,
  refine_with_llm TINYINT(1) NOT NULL DEFAULT 0,
  student_json LONGTEXT NULL,
  stats_json JSON NULL,
  llm_json LONGTEXT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_match_runs_user_resume_created (user_id, resume_id, created_at DESC),
  KEY idx_match_runs_user_goal_created (user_id, match_goal, created_at DESC),
  CONSTRAINT fk_match_runs_user_id
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS match_run_items (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  run_id BIGINT UNSIGNED NOT NULL,
  rank_index INT NOT NULL DEFAULT 0,
  job_id VARCHAR(191) NOT NULL,
  is_llm_top5 TINYINT(1) NOT NULL DEFAULT 0,
  job_json LONGTEXT NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_match_run_items_run_rank (run_id, rank_index),
  KEY idx_match_run_items_run_id (run_id),
  KEY idx_match_run_items_job_id (job_id),
  CONSTRAINT fk_match_run_items_run_id
    FOREIGN KEY (run_id) REFERENCES match_runs(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
