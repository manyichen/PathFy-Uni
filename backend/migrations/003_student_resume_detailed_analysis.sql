-- 能力画像：详细分析报告 JSON 落库，刷新页面后可从 /api/profile/result/:id 恢复
-- 在已存在 student_resume 的库上执行一次即可。

ALTER TABLE student_resume
  ADD COLUMN detailed_analysis LONGTEXT NULL COMMENT '能力画像详细分析报告 JSON' AFTER radar_html;
