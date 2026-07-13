# Alembic 数据库迁移

应用运行时仍使用 PyMySQL 和 `db_cursor()`；本目录只用 Alembic 管理数据库版本。

根目录中的 `002_*.sql`–`007_*.sql` 是切换 Alembic 前的历史迁移，只用于审计和旧环境排查，不再新增或直接执行。`versions/` 是新的唯一迁移链。

## 首次接入

初始 revision `20260712_0001` 包含 `schema.sql` 以及历史迁移 002–007 的完整最终结构。

- 新数据库：创建空数据库后直接执行 `alembic upgrade head`，迁移会在 `MYSQL_DATABASE` 指向的库中创建全部表并写入 MBTI 初始题目。
- 已有数据库：先执行 `python tools/verify_alembic_baseline.py`，确认通过后再执行 `alembic stamp 20260712_0001`。

不要对已有业务表的数据库直接运行初始 revision；必须先验证再 `stamp`，避免将不完整的旧结构误标为最新。

## 后续变更

项目没有 ORM metadata，因此 revision 必须人工编写，不能依赖 autogenerate：

```bash
cd backend
alembic revision -m "add example column"
# 审查并实现 upgrade() / downgrade()
alembic upgrade head
alembic current
alembic history
```

上线前应先在结构副本执行 upgrade/downgrade 测试。生产环境通常只执行 `alembic upgrade head`，禁止运行旧的 `run_migration_00x.py`。

`20260713_0002` 新增图谱更新任务、事件历史和写入 guard。部署 graph worker 前必须先升级到该 revision。
