"""HTTP transport. The real HTTPS transport is locked: it refuses to open any connection unless
``NETWORK_ENABLED_IN_THIS_BUILD`` is true *and* it was given a gate-issued, network-capable
``Authorization``. In this build the constant is false, so no code path can reach the network.

Tests use an in-memory transport implementing the same ``Transport`` protocol.
"""

from __future__ import annotations

import http.client
import ssl
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol
from urllib.parse import urlsplit

from wealthpilot.data import gdelt as _pkg
from wealthpilot.data.gdelt.config import Authorization, Limits, is_gate_issued
from wealthpilot.data.gdelt.errors import NetworkDisabledError

ARCHIVE_HOST = "data.gdeltproject.org"
ARCHIVE_PATH_PREFIX = "/gdeltv2/"
USER_AGENT = "wealthpilot-research-gdelt/0.1 (academic research; bounded sample)"


def archive_url(stamp: str) -> str:
    return f"https://{ARCHIVE_HOST}{ARCHIVE_PATH_PREFIX}{stamp}.gkg.csv.zip"


def same_resource(url: str, location: str) -> bool:
    """True only if ``location`` is the identical HTTPS resource (port 443 or default, no query)."""
    a, b = urlsplit(url), urlsplit(location)
    try:
        port = b.port
    except ValueError:
        return False
    return (b.scheme == "https" and (b.hostname or "").lower() == (a.hostname or "").lower()
            and port in (None, 443) and b.path == a.path and not b.query and not b.fragment)


@dataclass
class HttpResponse:
    status: int
    headers: dict[str, str]          # lower-case names
    body: bytes | None = None
    bytes_received: int = 0
    elapsed_ms: int = 0
    redirected_from: str | None = None

    def header(self, name: str) -> str | None:
        return self.headers.get(name.lower())


@dataclass
class TransportError(Exception):
    kind: str                         # timeout, connection_error, tls_error, redirect_rejected, body_incomplete,
                                      # aborted_by_budget
    detail: str = ""
    bytes_received: int = 0
    response: HttpResponse | None = field(default=None)

    def __str__(self) -> str:
        return f"{self.kind}: {self.detail}"


class Transport(Protocol):
    def head(self, url: str) -> HttpResponse: ...

    def get(self, url: str, max_bytes: int) -> HttpResponse: ...


class HttpsTransport:
    """Sequential, keep-alive HTTPS client on ``http.client``. No automatic redirects."""

    def __init__(self, authorization: Authorization, limits: Limits,
                 connection_factory: Callable[[], http.client.HTTPSConnection] | None = None) -> None:
        if not _pkg.NETWORK_ENABLED_IN_THIS_BUILD:
            raise NetworkDisabledError("network access is disabled in this build (B2-K)")
        if not (is_gate_issued(authorization) and authorization.network):
            raise NetworkDisabledError("no gate-issued network authorization")
        if authorization.mode == "full_acquisition":
            raise NetworkDisabledError("full acquisition is never authorized in this build")
        self.limits = limits
        self._factory = connection_factory or (lambda: http.client.HTTPSConnection(
            ARCHIVE_HOST, 443, timeout=limits.read_timeout_seconds, context=ssl.create_default_context()))
        self._conn: http.client.HTTPSConnection | None = None

    def _connection(self) -> http.client.HTTPSConnection:
        if self._conn is None:
            self._conn = self._factory()
        return self._conn

    def _request(self, method: str, url: str, max_bytes: int, redirected_from: str | None = None) -> HttpResponse:
        parts = urlsplit(url)
        if parts.scheme != "https" or parts.hostname != ARCHIVE_HOST or not parts.path.startswith(ARCHIVE_PATH_PREFIX):
            raise TransportError("redirect_rejected", f"refusing URL outside the archive: {url}")
        start = time.monotonic()
        received = 0
        try:
            conn = self._connection()
            conn.request(method, parts.path, headers={"User-Agent": USER_AGENT, "Accept-Encoding": "identity"})
            resp = conn.getresponse()
            headers = {k.lower(): v for k, v in resp.getheaders()}
            if 300 <= resp.status < 400:
                resp.read()
                location = headers.get("location", "")
                if redirected_from is None and same_resource(url, location):
                    return self._request(method, url, max_bytes, redirected_from=url)
                raise TransportError("redirect_rejected", f"{resp.status} to {location!r}")
            body = None
            if method == "GET":
                declared = headers.get("content-length")
                if declared is not None and declared.isdigit() and int(declared) > max_bytes:
                    self.close()
                    raise TransportError("aborted_by_budget", f"Content-Length {declared} > {max_bytes}")
                chunks = []
                while True:
                    chunk = resp.read(1024 * 1024)
                    if not chunk:
                        break
                    received += len(chunk)
                    if received > max_bytes:
                        self.close()
                        raise TransportError("aborted_by_budget", f"body exceeded {max_bytes} B", received)
                    chunks.append(chunk)
                body = b"".join(chunks)
            else:
                resp.read()
            return HttpResponse(resp.status, headers, body, received, int((time.monotonic() - start) * 1000),
                                redirected_from)
        except TransportError:
            raise
        except TimeoutError as exc:
            self.close()
            raise TransportError("timeout", str(exc), received) from exc
        except ssl.SSLError as exc:
            self.close()
            raise TransportError("tls_error", str(exc), received) from exc
        except http.client.IncompleteRead as exc:
            self.close()
            raise TransportError("body_incomplete", str(exc), received + len(exc.partial)) from exc
        except (OSError, http.client.HTTPException) as exc:
            self.close()
            raise TransportError("connection_error", f"{type(exc).__name__}", received) from exc

    def head(self, url: str) -> HttpResponse:
        return self._request("HEAD", url, 0)

    def get(self, url: str, max_bytes: int) -> HttpResponse:
        return self._request("GET", url, max_bytes)

    def close(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            finally:
                self._conn = None
