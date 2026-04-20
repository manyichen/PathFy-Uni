-- 生涯报告 M1：报告快照 / 目标职业 / 评估周期
-- 在已有 users 表的数据库上执行一次即可。

CREATE TABLE IF NOT EXISTS career_reports (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id BIGINT UNSIGNED NOT NULL,
  resume_id BIGINT UNSIGNED NOT NULL,
  title VARCHAR(160) NOT NULL,
  primary_job_id VARCHAR(191) NULL,
  target_job_ids_json JSON NOT NULL,
  report_json LONGTEXT NOT NULL,
  meta_json JSON NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_career_reports_user_id_created_at (user_id, created_at DESC),
  CONSTRAINT fk_career_reports_user_id
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS career_report_targets (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  report_id BIGINT UNSIGNED NOT NULL,
  job_id VARCHAR(191) NOT NULL,
  title VARCHAR(191) NULL,
  is_primary TINYINT(1) NOT NULL DEFAULT 0,
  target_order INT NOT NULL DEFAULT 0,
  source VARCHAR(32) NOT NULL DEFAULT 'manual',
  meta_json JSON NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_report_job (report_id, job_id),
  KEY idx_career_report_targets_report_id_order (report_id, target_order),
  CONSTRAINT fk_career_report_targets_report_id
    FOREIGN KEY (report_id) REFERENCES career_reports(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS career_report_reviews (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  report_id BIGINT UNSIGNED NOT NULL,
  review_cycle VARCHAR(32) NOT NULL DEFAULT 'biweekly',
  metrics_json JSON NOT NULL,
  adjustment_json JSON NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_career_report_reviews_report_id_created_at (report_id, created_at DESC),
  CONSTRAINT fk_career_report_reviews_report_id
    FOREIGN KEY (report_id) REFERENCES career_reports(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
