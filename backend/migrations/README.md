# Alembic 数据库迁移

应用运行时仍使用 PyMySQL 和 `db_cursor()`；本目录只用 Alembic 管理数据库版本。

根目录中的 `002_*.sql`–`007_*.sql` 是切换 Alembic 前的历史迁移，只用于审计和旧环境排查，不再新增或直接执行。`versions/` 是新的唯一迁移链。

## 首次接入

当前 Alembic 基线 `20260712_0001` 表示数据库已经包含 `schema.sql` 以及历史迁移 002–007。

- 新数据库：先导入 `schema.sql`，然后执行 `alembic stamp 20260712_0001`。
- 已有数据库：先执行 `python tools/verify_alembic_baseline.py`，确认通过后再执行 `alembic stamp 20260712_0001`。

不要在空数据库上直接 `alembic upgrade head`：基线 revision 不负责重建历史 schema。

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
