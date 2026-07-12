from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.db.alembic_config import database_url

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# This project intentionally keeps handwritten SQL repositories and has no ORM
# model metadata. New revisions are therefore reviewed and written explicitly.
target_metadata = None
# Alembic stores options in ConfigParser, where percent-encoded URL characters
# must be escaped to survive interpolation.
database_url_text = database_url().render_as_string(hide_password=False).replace("%", "%%")
config.set_main_option("sqlalchemy.url", database_url_text)


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        transaction_per_migration=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            transaction_per_migration=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
