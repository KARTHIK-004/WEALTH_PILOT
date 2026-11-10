"""Provider-neutral adapter interface. **No concrete provider exists, and none is selected here.**

``ADAPTERS`` is empty. Writing and registering an adapter for a specific provider is a separate change that
needs approval Gate B (provider and model). ``DisabledProvider`` is what a dry run uses: calling it raises, so a
dry run provably makes no model call. Tests inject their own scripted fake that implements ``SuggestionProvider``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from wealthpilot.data.gdelt.errors import GdeltToolError

RETRYABLE_KINDS = frozenset({"timeout", "rate_limited", "server_error"})
ALL_KINDS = RETRYABLE_KINDS | {"refused", "auth", "bad_request", "unknown"}


class ExecutionBlocked(GdeltToolError):
    """AI execution is blocked: a gate, approval, lock or adapter is missing."""

    code = "ai_execution_blocked"

    def __init__(self, reason: str, problems: tuple[str, ...] = ()) -> None:
        super().__init__(reason)
        self.problems = problems


class ProviderNotImplemented(ExecutionBlocked):
    code = "ai_provider_not_implemented"


@dataclass(frozen=True)
class SuggestionRequest:
    """One provider call for one item. Contains only the approved input fields (inside ``user``)."""

    item_id: str
    system: str
    user: str
    response_schema: dict[str, Any]
    max_output_tokens: int
    temperature: float | None = None     # the approved, effective value; an adapter must pass exactly this or refuse


@dataclass
class ProviderResponse:
    text: str
    model_id: str
    model_version: str | None = None
    request_id: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    latency_ms: int | None = None


class ProviderError(Exception):
    """A provider failure. ``kind`` decides whether a retry is allowed."""

    def __init__(self, kind: str, detail: str = "") -> None:
        super().__init__(f"{kind}: {detail}")
        self.kind = kind if kind in ALL_KINDS else "unknown"
        self.detail = detail

    @property
    def retryable(self) -> bool:
        return self.kind in RETRYABLE_KINDS


class SuggestionProvider(Protocol):
    name: str

    def suggest(self, request: SuggestionRequest) -> ProviderResponse: ...


class DisabledProvider:
    """Used by dry runs and by default. Any call raises."""

    name = "disabled"

    def suggest(self, request: SuggestionRequest) -> ProviderResponse:
        raise ExecutionBlocked("the provider is disabled: no model call can be made")


# provider name -> factory(config, authorization) -> SuggestionProvider. Empty by design.
ADAPTERS: dict[str, Callable[..., SuggestionProvider]] = {}


def build_provider(name: str | None, *factory_args: Any) -> SuggestionProvider:
    if not name:
        raise ProviderNotImplemented("no provider is configured: choosing one is approval Gate B")
    factory = ADAPTERS.get(name)
    if factory is None:
        raise ProviderNotImplemented(
            f"no adapter exists for provider {name!r}. Adding one is a separate change that needs approval "
            "Gate B (provider and model); none is registered in this build")
    return factory(*factory_args)
