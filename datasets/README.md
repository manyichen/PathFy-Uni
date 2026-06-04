# datasets 目录说明

本目录用于**岗位/招聘类数据集**（如 `jobs.csv`、Excel 原始表），可纳入 Git 做项目复现。

## 禁止提交的内容

以下文件含**真实用户隐私**，仅保存在本机或服务器，**勿 `git add` / 勿 push**：

| 类型 | 示例 | 原因 |
|------|------|------|
| MySQL 全库导出 | `suilli_mizi.sql` | 含密码哈希、邮箱、完整简历 |
| 脱敏前的 dump | `*.dump`、`backup/*.sql` | 同上 |
| SSH 私钥 | `*.pem`、`id_rsa` | 服务器访问凭证 |

`.gitignore` 已忽略 `datasets/**/*.sql` 等模式；若仍出现在 `git status`，说明不要提交。

## 允许提交的内容

- 岗位/招聘结构化数据：`jobs.csv`、招聘 Excel（无用户账号数据）
- 说明文档、字段字典

## 初始化数据库请用

不要用 `datasets/*.sql` 灌库，请使用仓库内**无用户数据**的脚本：

```bash
mysql -u ... -p suilli_mizi < backend/schema.sql
mysql -u ... -p suilli_mizi < backend/migrations/002_student_resume_cap_conf.sql
# ... 003、004、005 按顺序
```

## 本地需要备份生产库时

1. Navicat 导出到本目录（如 `suilli_mizi.sql`）— 仅本地保留  
2. 不要提交；不要放到公开网盘  
3. 与团队共享测试数据时，先做**脱敏**（见下）

## 脱敏 dump 思路（可选）

在**副本库**中执行后再导出，例如：

```sql
UPDATE users SET email = CONCAT('user', id, '@test.local');
-- 视需要清空或缩短 student_resume.resume_text
-- 视需要清空 ai_chat_messages.content
```

## 若误将含隐私文件 push 到远程

1. 从仓库历史中移除该文件（`git filter-repo` 或 BFG）  
2. 通知相关用户**修改密码**  
3. 轮换曾出现在文件中的 API Key / 数据库密码  
4. 假定邮箱、简历片段可能已泄露

## 协作规范

- 截图、答辩 PPT：邮箱、手机、简历正文打码  
- Issue / 聊天：不发 dump、`.env`、私钥  
- 开发环境使用脱敏库或空库 + `schema.sql`，勿用生产全量导入
