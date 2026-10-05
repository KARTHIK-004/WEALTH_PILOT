"""Shared fixture for DB round-trip tests.

Binds a session to a single connection wrapped in an outer transaction that
is rolled back after every test, so the test suite never leaves rows behind
in TEST_DATABASE_URL and tests can run repeatedly without accumulating data.
Uses TEST_DATABASE_URL exclusively — never DATABASE_URL — so the test suite
can never touch development data.

A plain `connection.begin()` breaks the moment a test itself calls
`session.rollback()` (e.g. after catching an expected IntegrityError): the
Session's rollback also ends the connection's outer transaction, so the
fixture's own teardown rollback then warns "transaction already
deassociated from connection". The standard SQLAlchemy 2.0 fix is a SAVEPOINT
that gets restarted every time the Session ends its own transaction — see
https://docs.sqlalchemy.org/en/20/orm/session_transaction.html#joining-a-session-into-an-external-transaction-such-as-for-test-suites
"""

import pytest
from sqlalchemy.orm import Session

from wealthpilot.config import get_settings
from wealthpilot.db.session import get_engine


@pytest.fixture()
def db_session():
    settings = get_settings()
    assert settings.test_database_url, "TEST_DATABASE_URL is not set — see .env.example"

    engine = get_engine(settings.test_database_url)
    connection = engine.connect()
    outer_transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")

    try:
        yield session
    finally:
        session.close()
        outer_transaction.rollback()
        connection.close()
        engine.dispose()
