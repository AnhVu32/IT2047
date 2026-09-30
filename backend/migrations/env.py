from __future__ import annotations

import os
from logging.config import fileConfig
from typing import Union

from alembic import context
from dotenv import find_dotenv, load_dotenv
from sqlalchemy import create_engine, pool, text
from sqlalchemy.engine import URL


config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

load_dotenv(find_dotenv())

# This project currently uses SQL directly instead of declarative ORM models.
# Revisions are therefore explicit; autogenerate is intentionally disabled.
target_metadata = None


def database_url() -> Union[str, URL]:
    explicit_url = os.getenv("DATABASE_URL")
    if explicit_url:
        return explicit_url

    required = {
        "username": os.getenv("USERNAME_DB"),
        "password": os.getenv("PASSWORD_DB"),
        "host": os.getenv("HOST_DB"),
        "port": os.getenv("PORT_DB", "5432"),
        "database": os.getenv("DATABASE"),
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise RuntimeError(
            "Missing database configuration for Alembic: " + ", ".join(missing)
        )

    return URL.create(
        drivername="postgresql+psycopg2",
        username=required["username"],
        password=required["password"],
        host=required["host"],
        port=int(required["port"]),
        database=required["database"],
    )


def run_migrations_offline() -> None:
    url = database_url()
    if isinstance(url, URL):
        url = url.render_as_string(hide_password=False)
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(database_url(), poolclass=pool.NullPool)

    with connectable.connect() as connection:
        # Serializes migrations when multiple application containers start at once.
        connection.execute(text("SELECT pg_advisory_lock(2307001)"))
        try:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                compare_type=True,
            )

            with context.begin_transaction():
                context.run_migrations()
        finally:
            connection.execute(text("SELECT pg_advisory_unlock(2307001)"))

    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
