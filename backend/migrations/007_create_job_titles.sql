-- 007: 岗位名称实体表（从招聘数据导入时同步维护）
CREATE TABLE IF NOT EXISTS `job_titles` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `title` VARCHAR(191) NOT NULL,
  `record_count` INT NOT NULL DEFAULT 0,
  `company_count` INT NOT NULL DEFAULT 0,
  `job_code_count` INT NOT NULL DEFAULT 0,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_job_titles_title` (`title`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
