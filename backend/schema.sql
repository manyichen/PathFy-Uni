CREATE DATABASE IF NOT EXISTS `suilli_mizi`
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE `suilli_mizi`;

CREATE TABLE IF NOT EXISTS `users` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `username` VARCHAR(32) NOT NULL,
  `email` VARCHAR(191) NOT NULL,
  `password_hash` VARCHAR(255) NOT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `last_login_at` DATETIME NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_users_username` (`username`),
  UNIQUE KEY `uk_users_email` (`email`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `ai_chat_sessions` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `user_id` BIGINT UNSIGNED NOT NULL,
  `title` VARCHAR(120) NOT NULL DEFAULT '新对话',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `last_message_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_ai_chat_sessions_user_id_last_message_at` (`user_id`, `last_message_at` DESC),
  CONSTRAINT `fk_ai_chat_sessions_user_id`
    FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `ai_chat_messages` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `session_id` BIGINT UNSIGNED NOT NULL,
  `role` VARCHAR(16) NOT NULL,
  `content` TEXT NOT NULL,
  `filters_json` JSON NULL,
  `result_job_ids_json` JSON NULL,
  `is_saved` TINYINT(1) NOT NULL DEFAULT 0,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_ai_chat_messages_session_id_created_at` (`session_id`, `created_at` ASC),
  KEY `idx_ai_chat_messages_is_saved` (`is_saved`),
  CONSTRAINT `fk_ai_chat_messages_session_id`
    FOREIGN KEY (`session_id`) REFERENCES `ai_chat_sessions` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- 创建学生简历表（user_id 与 users.id 同为 BIGINT UNSIGNED，外键兼容）
CREATE TABLE IF NOT EXISTS student_resume (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT UNSIGNED NOT NULL,
    name VARCHAR(50) NOT NULL,
    major VARCHAR(100) NOT NULL,
    resume_text TEXT,
    cap_req_theory TINYINT DEFAULT 0,
    cap_req_cross TINYINT DEFAULT 0,
    cap_req_practice TINYINT DEFAULT 0,
    cap_req_digital TINYINT DEFAULT 0,
    cap_req_innovation TINYINT DEFAULT 0,
    cap_req_teamwork TINYINT DEFAULT 0,
    cap_req_social TINYINT DEFAULT 0,
    cap_req_growth TINYINT DEFAULT 0,
    cap_conf_theory DECIMAL(6,4) NOT NULL DEFAULT 0.5500,
    cap_conf_cross DECIMAL(6,4) NOT NULL DEFAULT 0.5500,
    cap_conf_practice DECIMAL(6,4) NOT NULL DEFAULT 0.5500,
    cap_conf_digital DECIMAL(6,4) NOT NULL DEFAULT 0.5500,
    cap_conf_innovation DECIMAL(6,4) NOT NULL DEFAULT 0.5500,
    cap_conf_teamwork DECIMAL(6,4) NOT NULL DEFAULT 0.5500,
    cap_conf_social DECIMAL(6,4) NOT NULL DEFAULT 0.5500,
    cap_conf_growth DECIMAL(6,4) NOT NULL DEFAULT 0.5500,
    completeness TINYINT DEFAULT 0,
    competitiveness TINYINT DEFAULT 0,
    radar_html TEXT,
    detailed_analysis LONGTEXT NULL COMMENT '能力画像详细分析报告 JSON',
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_student_resume_user_id
      FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- 创建性格测试题目表
CREATE TABLE IF NOT EXISTS personality_test_questions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    question_text TEXT NOT NULL,
    option_a TEXT NOT NULL,
    option_b TEXT NOT NULL,
    dimension VARCHAR(20) NOT NULL,
    option_a_type VARCHAR(1) NOT NULL,
    option_b_type VARCHAR(1) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 创建性格测试答案表
CREATE TABLE IF NOT EXISTS personality_test_answers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT UNSIGNED NOT NULL,
    question_id INT NOT NULL,
    user_choice VARCHAR(1) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_personality_answers_user_id
      FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_personality_answers_question_id
      FOREIGN KEY (question_id) REFERENCES personality_test_questions(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 创建人物画像表
CREATE TABLE IF NOT EXISTS personality_profiles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT UNSIGNED NOT NULL,
    mbti_type VARCHAR(4) NOT NULL,
    personality_analysis TEXT NOT NULL,
    recommended_jobs TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_personality_profiles_user_id
      FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 插入 MBTI 性格测试题目（50 题）；仅当表中尚无题目时插入，重复执行本文件不会产生重复题目
INSERT INTO personality_test_questions (question_text, option_a, option_b, dimension, option_a_type, option_b_type)
SELECT q, a, b, d, ta, tb FROM (
  SELECT '我更倾向从以下何处获得力量' AS q, '朋友和家人' AS a, '个人的内心想法' AS b, 'EI' AS d, 'E' AS ta, 'I' AS tb
  UNION ALL SELECT '大多数人会说你是一个', '非常坦诚开放的人', '重视自我隐私的人', 'EI', 'E', 'I'
  UNION ALL SELECT '你通常', '与人容易混熟', '比较沉静和矜持', 'EI', 'E', 'I'
  UNION ALL SELECT '在一大人群当中，通常是', '你介绍大家认识', '别人介绍你', 'EI', 'E', 'I'
  UNION ALL SELECT '你喜欢花很多的时间', '和别人在一起', '一个人独处', 'EI', 'E', 'I'
  UNION ALL SELECT '你认为别人一般', '用很短的时间便认识你', '要花很长时间才认识你', 'EI', 'E', 'I'
  UNION ALL SELECT '和一群人在一起，你通常会选', '参与大伙儿的谈话', '跟你很熟络的人个别谈话', 'EI', 'E', 'I'
  UNION ALL SELECT '你是否', '容易让人了解', '难于让人了解', 'EI', 'E', 'I'
  UNION ALL SELECT '在社交聚会中，你会', '是说话很多的一个', '让别人多说话', 'EI', 'E', 'I'
  UNION ALL SELECT '你是否', '可以与任何人按需要从容地交谈', '只是对某些人或在某种情况下才可以畅所欲言', 'EI', 'E', 'I'
  UNION ALL SELECT '我更倾向于', '坦率开放', '着重隐私', 'EI', 'E', 'I'
  UNION ALL SELECT '我更倾向于', '健谈', '矜持', 'EI', 'E', 'I'
  UNION ALL SELECT '选择较符合你的词', '朋友众多', '朋友不多', 'EI', 'E', 'I'
  UNION ALL SELECT '你更倾向于', '爱合群', '文静', 'EI', 'E', 'I'
  UNION ALL SELECT '假如你是一位老师，你会选择', '以事实为主的课程', '涉及理论的课程', 'SN', 'S', 'N'
  UNION ALL SELECT '要做许多人也做的事，你比较喜欢', '按照认可的方法去做', '构想一个自己的方法', 'SN', 'S', 'N'
  UNION ALL SELECT '你会', '跟随一些证明有效地方法', '分析还有什么毛病，及针对尚未解决的难题', 'SN', 'S', 'N'
  UNION ALL SELECT '哪些人会更吸引你', '实事求是，具丰富常识的人', '一个思想敏捷及非常聪颖的人', 'SN', 'S', 'N'
  UNION ALL SELECT '你更倾向于选择哪组词', '肯定', '理论', 'SN', 'S', 'N'
  UNION ALL SELECT '你更倾向于选择哪组词', '实况', '意念', 'SN', 'S', 'N'
  UNION ALL SELECT '你更喜欢', '以事论事', '富想象的', 'SN', 'S', 'N'
  UNION ALL SELECT '你更倾向于选择', '真实的', '想象的', 'SN', 'S', 'N'
  UNION ALL SELECT '你更善于考虑事件的', '必然性', '可能性', 'SN', 'S', 'N'
  UNION ALL SELECT '你更倾向于选择', '事实', '意念', 'SN', 'S', 'N'
  UNION ALL SELECT '选择较符合你的词', '务实的', '理论的', 'SN', 'S', 'N'
  UNION ALL SELECT '选择较符合你的词', '合情合理', '令人着迷', 'SN', 'S', 'N'
  UNION ALL SELECT '你更倾向于选择', '制造', '创造', 'SN', 'S', 'N'
  UNION ALL SELECT '你是否经常让', '你的理智主宰你的情感', '你的情感支配你的理智', 'TF', 'T', 'F'
  UNION ALL SELECT '你倾向', '重视逻辑多于情感', '重视感情多于逻辑', 'TF', 'T', 'F'
  UNION ALL SELECT '要做决定时，你认为比较重要的是', '据事实衡量', '考虑他人的感受和意见', 'TF', 'T', 'F'
  UNION ALL SELECT '选择更符合你的词', '公正', '敏感', 'TF', 'T', 'F'
  UNION ALL SELECT '选择更符合你的词', '远见', '同情怜悯', 'TF', 'T', 'F'
  UNION ALL SELECT '选择更符合你的词', '客观的', '亲切的', 'TF', 'T', 'F'
  UNION ALL SELECT '你更倾向于', '分析', '同情', 'TF', 'T', 'F'
  UNION ALL SELECT '选择更符合你的词', '有决心的', '全心投入的', 'TF', 'T', 'F'
  UNION ALL SELECT '选择更符合你的词', '客观的', '热情的', 'TF', 'T', 'F'
  UNION ALL SELECT '选择更符合你的词', '坚持己见', '温柔有爱心', 'TF', 'T', 'F'
  UNION ALL SELECT '当你要出外一整天，你会不会', '计划你要做什么和在什么时候做', '说去就去', 'JP', 'J', 'P'
  UNION ALL SELECT '当你有一份特别的任务，你会喜欢', '开始前小心组织计划', '边做边找须做什么', 'JP', 'J', 'P'
  UNION ALL SELECT '你比较喜欢', '很早便把约会、社交聚集等事情安排妥当', '无拘无束，看当时有什么好玩就做什么', 'JP', 'J', 'P'
  UNION ALL SELECT '当你要在一个星期内完成一个大项目，你在开始时候就会', '把要做的不同工作依次列出', '马上动工', 'JP', 'J', 'P'
  UNION ALL SELECT '总的来说，要做一个大型作业时，你会选', '首先把工作按步细分', '边做边想该做什么', 'JP', 'J', 'P'
  UNION ALL SELECT '在日常工作中，你会', '通常预先计划，以免要在压力下工作', '颇为喜欢处理迫使你分秒必争的突发事件', 'JP', 'J', 'P'
  UNION ALL SELECT '你认为按照程序表做事', '大多数情况下是有帮助而且是你喜欢做的', '有时是需要的，但一般来说你不大喜欢这样做', 'JP', 'J', 'P'
  UNION ALL SELECT '你做事多数是', '照拟好的程序表去做', '按当天心情去做', 'JP', 'J', 'P'
  UNION ALL SELECT '按照程序表做事', '合你心意', '令你感到束缚', 'JP', 'J', 'P'
  UNION ALL SELECT '你更倾向于哪个', '预先安排的', '无计划的', 'JP', 'J', 'P'
  UNION ALL SELECT '你更倾向于哪个', '有条不紊', '不拘小节', 'JP', 'J', 'P'
  UNION ALL SELECT '你更倾向于哪个', '预先安排', '不受约束', 'JP', 'J', 'P'
  UNION ALL SELECT '你更倾向于哪个', '决定', '冲动', 'JP', 'J', 'P'
) AS seed
WHERE (SELECT COUNT(*) FROM personality_test_questions) = 0;

-- 生涯报告 M1：报告快照 / 目标职业 / 评估记录
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

-- 人岗匹配快照（报告页可复用最近匹配结果）
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