"""Exception types. Every refusal carries a machine-readable ``code`` and a human reason."""

from __future__ import annotations


class GdeltToolError(Exception):
    """Base class for every error raised by this package."""

    code = "gdelt_error"

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class InvalidTimestampError(GdeltToolError, ValueError):
    """A timestamp is malformed, off the 15-minute grid, or timezone-naive/ambiguous."""

    code = "invalid_timestamp"


class ConfigError(GdeltToolError):
    """The run configuration is missing, malformed, or asks for something not allowed."""

    code = "config_error"


class ApprovalRefused(GdeltToolError):
    """An approval gate refused the requested mode."""

    code = "approval_refused"


class NetworkDisabledError(GdeltToolError):
    """A network operation was attempted in a build or context where it is disabled."""

    code = "network_disabled"


class BudgetExceeded(GdeltToolError):
    """A byte, request, disk or temporary-disk limit would be (or was) exceeded."""

    code = "budget_exceeded"

    def __init__(self, reason: str, *, limit: str) -> None:
        super().__init__(reason)
        self.limit = limit


class IntegrityError(GdeltToolError):
    """A downloaded body failed a size, checksum, zip-structure or CRC check."""

    code = "integrity_error"

    def __init__(self, reason: str, *, status: str) -> None:
        super().__init__(reason)
        self.status = status  # one of manifest validation_status values


class InvalidTransition(GdeltToolError):
    """A manifest state change that the state machine does not allow."""

    code = "invalid_transition"


class SampleIntegrityError(GdeltToolError):
    """A pre-registered sample list does not match its committed SHA-256, or is unavailable."""

    code = "sample_integrity"


class FilterSpecError(GdeltToolError):
    """A filter specification does not match its registered version hash, or is malformed."""

    code = "filter_spec"


class UnsafePathError(GdeltToolError):
    """A path operation outside the allowed folders, through a symlink, or on an unexpected name."""

    code = "unsafe_path"
