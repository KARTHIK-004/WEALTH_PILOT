"""Pure safety logic for running the isolated database-backed tests (no I/O, no database, no secrets in any message).

`resolve_target` decides whether `TEST_DATABASE_URL` may be used. It accepts exactly one destination: database `neondb_test` on a known Neon host that equals the expected host
(taken from `--expected-host` / `WEALTHPILOT_EXPECTED_TEST_DB_HOST`, else from the host of `DATABASE_URL`). Everything else -- missing, empty, unparsable, another database name (including
the development database `neondb`), an unknown host, several hosts, a query string that could override host or database, or no way to confirm the expected host -- raises
`UnsafeTargetError` BEFORE any database-writing operation. The error text and the returned `Target` never contain a password or a URL.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import parse_qsl, urlsplit

EXPECTED_DATABASE = "neondb_test"
DEVELOPMENT_DATABASES = ("neondb",)
ALLOWED_HOST_SUFFIXES = (".neon.tech",)
ACCEPTED_SCHEMES = ("postgresql", "postgres", "postgresql+psycopg")
FORBIDDEN_QUERY_KEYS = frozenset({"host", "hostaddr", "dbname", "service"})   # libpq lets these override the URL's own host/database
DEFAULT_KEEPALIVE = {"keepalives_idle": 20, "keepalives_interval": 5, "keepalives_count": 3, "tcp_user_timeout": 30000}


class UnsafeTargetError(Exception):
    """The database target is missing, ambiguous or not the isolated test database. The message never contains a URL or password."""


@dataclass(frozen=True)
class Target:
    host: str
    database: str

    def describe(self) -> str:
        return f"host={self.host} database={self.database}"


def _parse(url: str, label: str):
    try:
        parts = urlsplit(url.strip())
        _ = parts.port   # raises ValueError on a malformed port
    except ValueError:
        raise UnsafeTargetError(f"{label} is not a parseable database URL") from None
    if parts.scheme not in ACCEPTED_SCHEMES:
        raise UnsafeTargetError(f"{label} must be a PostgreSQL URL")
    return parts


def _host_of(parts, label: str) -> str:
    hostinfo = parts.netloc.rsplit("@", 1)[-1]
    if "," in hostinfo:
        raise UnsafeTargetError(f"{label} lists several hosts; the target is ambiguous")
    if not parts.hostname:
        raise UnsafeTargetError(f"{label} has no host")
    return parts.hostname.lower()


def resolve_target(
    test_url: str | None,
    development_url: str | None = None,
    expected_host: str | None = None,
    *,
    expected_database: str = EXPECTED_DATABASE,
    allowed_host_suffixes: tuple[str, ...] = ALLOWED_HOST_SUFFIXES,
) -> Target:
    if test_url is None or not test_url.strip():
        raise UnsafeTargetError("TEST_DATABASE_URL is not set (or is empty); refusing to choose a database")
    parts = _parse(test_url, "TEST_DATABASE_URL")
    keys = {k.lower() for k, _ in parse_qsl(parts.query, keep_blank_values=True)}
    if keys & FORBIDDEN_QUERY_KEYS:
        raise UnsafeTargetError("TEST_DATABASE_URL has a query parameter that can override the host or database; the target is ambiguous")
    host = _host_of(parts, "TEST_DATABASE_URL")
    database = parts.path.lstrip("/")
    if not database or "/" in database:
        raise UnsafeTargetError("TEST_DATABASE_URL does not name exactly one database")
    if database in DEVELOPMENT_DATABASES:
        raise UnsafeTargetError(f"TEST_DATABASE_URL points at the development database '{database}'; refusing")
    if database != expected_database:
        raise UnsafeTargetError(f"the database name must be exactly '{expected_database}', not '{database}'")
    if not any(host.endswith(suffix) for suffix in allowed_host_suffixes):
        raise UnsafeTargetError("the host is not a known Neon host")
    if expected_host:
        wanted = expected_host.strip().lower()
    elif development_url and development_url.strip():
        wanted = _host_of(_parse(development_url, "DATABASE_URL"), "DATABASE_URL")
    else:
        raise UnsafeTargetError("cannot confirm the expected host: set --expected-host (or WEALTHPILOT_EXPECTED_TEST_DB_HOST) or provide DATABASE_URL")
    if host != wanted:
        raise UnsafeTargetError("the host differs from the expected host")
    return Target(host=host, database=database)


def check_engine_target(url_host: str | None, url_database: str | None, target: Target) -> None:
    """Used by the pytest plugin on every engine the tests create: only the resolved target is allowed."""
    if (url_host or "").lower() != target.host or url_database != target.database:
        raise UnsafeTargetError("BLOCKED: a test tried to open an engine to a database other than the resolved isolated test database")


def keepalive_connect_args(enabled: bool = True, **overrides: int) -> dict[str, int]:
    """libpq TCP keepalive / user-timeout parameters for the TEST connection only (psycopg 3 passes them straight to libpq). Empty when disabled."""
    if not enabled:
        return {}
    unknown = set(overrides) - set(DEFAULT_KEEPALIVE)
    if unknown:
        raise ValueError(f"unknown keepalive setting(s): {sorted(unknown)}")
    merged = {**DEFAULT_KEEPALIVE, **{k: int(v) for k, v in overrides.items()}}
    if any(v <= 0 for v in merged.values()):
        raise ValueError("keepalive settings must be positive integers")
    return {"keepalives": 1, **merged, "connect_timeout": 20}


DEVELOPMENT_FIXTURES = frozenset({"real_client", "real_db_session", "real_db_connection", "real_session", "real_customer_id", "real_external_id"})


def uses_development_database(fixture_names) -> bool:
    """A test whose fixture closure includes any of these reads DATABASE_URL (the development database) and is never run by the isolated runner."""
    return bool(DEVELOPMENT_FIXTURES & set(fixture_names))


def parse_env_file(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in text.splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip().strip("\"'")
    return values


_URL_RE = re.compile(r"postgres(?:ql)?(?:\+\w+)?://\S+", re.IGNORECASE)


def redact(text: str, *secrets: str | None) -> str:
    """Remove URLs and any given secret strings from text before it is printed."""
    for secret in secrets:
        if secret:
            text = text.replace(secret, "<redacted>")
    return _URL_RE.sub("<url>", text)
