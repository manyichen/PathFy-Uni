-- 能力画像与人岗匹配长期方案：八维置信度落库（与 Neo4j 岗位 cap_conf_* 刻度一致 0~1）
-- 在已存在 student_resume 的库上执行一次即可。

ALTER TABLE student_resume
  ADD COLUMN cap_conf_theory DECIMAL(6,4) NOT NULL DEFAULT 0.5500 AFTER cap_req_growth,
  ADD COLUMN cap_conf_cross DECIMAL(6,4) NOT NULL DEFAULT 0.5500 AFTER cap_conf_theory,
  ADD COLUMN cap_conf_practice DECIMAL(6,4) NOT NULL DEFAULT 0.5500 AFTER cap_conf_cross,
  ADD COLUMN cap_conf_digital DECIMAL(6,4) NOT NULL DEFAULT 0.5500 AFTER cap_conf_practice,
  ADD COLUMN cap_conf_innovation DECIMAL(6,4) NOT NULL DEFAULT 0.5500 AFTER cap_conf_digital,
  ADD COLUMN cap_conf_teamwork DECIMAL(6,4) NOT NULL DEFAULT 0.5500 AFTER cap_conf_innovation,
  ADD COLUMN cap_conf_social DECIMAL(6,4) NOT NULL DEFAULT 0.5500 AFTER cap_conf_teamwork,
  ADD COLUMN cap_conf_growth DECIMAL(6,4) NOT NULL DEFAULT 0.5500 AFTER cap_conf_social;
