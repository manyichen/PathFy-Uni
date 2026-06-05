-- 006: 用户表增加管理员标识
ALTER TABLE users ADD COLUMN is_admin TINYINT(1) NOT NULL DEFAULT 0 AFTER last_login_at;
