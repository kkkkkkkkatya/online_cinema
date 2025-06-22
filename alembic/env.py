import asyncio
from logging.config import fileConfig
from dotenv import load_dotenv
import os

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import AsyncEngine
from alembic import context

from app.db.models.base import Base  # імпорт твоїх моделей
from app.db import models  # імпорт моделей для реєстрації

load_dotenv()

# Завантажуємо конфігурацію Alembic
config = context.config
fileConfig(config.config_file_name)

# Встановлюємо url з env (або з alembic.ini)
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set")

config.set_main_option("sqlalchemy.url", DATABASE_URL)

target_metadata = Base.metadata


def run_migrations_offline():
    """Міграції в offline режимі — генеруємо SQL без підключення."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    """Синхронний запуск міграцій."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online():
    """Асинхронний запуск міграцій із AsyncEngine."""
    from sqlalchemy.ext.asyncio import create_async_engine

    connectable = create_async_engine(
        config.get_main_option("sqlalchemy.url"),
        poolclass=pool.NullPool,
        future=True,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online_sync():
    """Запускаємо асинхронний код через asyncio.run()."""
    asyncio.run(run_migrations_online())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online_sync()
