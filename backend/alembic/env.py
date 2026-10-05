import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# Import models so Base.metadata is fully populated before autogenerate runs.
from wealthpilot.config import get_settings
from wealthpilot.db.base import Base
from wealthpilot.db.session import to_sqlalchemy_url
import wealthpilot.db.models  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# The URL is never read from alembic.ini — it comes from the same Settings
# object the app uses, so migrations and the app can never point at a
# different database than the app through a stale ini file. Set
# ALEMBIC_TARGET=test (e.g. `ALEMBIC_TARGET=test alembic upgrade head`) to
# run against TEST_DATABASE_URL instead of DATABASE_URL — used by the test
# suite and by the Phase 1 completion check, never by the running app.
settings = get_settings()
_raw_url = settings.test_database_url if os.environ.get("ALEMBIC_TARGET") == "test" else settings.database_url
config.set_main_option("sqlalchemy.url", to_sqlalchemy_url(_raw_url))


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
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
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
