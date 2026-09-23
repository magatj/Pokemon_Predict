"""Common source-adapter interface.

Every adapter implements the same three methods so sources are independently
replaceable and jobs never need to know which one they are talking to.
"""
from __future__ import annotations

from typing import Any, List

try:  # pragma: no cover - typing_extensions fallback for older runtimes
    from typing import Protocol, runtime_checkable
except ImportError:  # pragma: no cover
    from typing_extensions import Protocol, runtime_checkable  # type: ignore

from pokevend.models import SourceHealth


@runtime_checkable
class DataSource(Protocol):
    """Contract shared by machine-discovery and observation sources."""

    name: str
    authority: str

    def fetch(self) -> Any:
        """Retrieve raw payloads. May raise SourceSkipped."""
        ...

    def normalize(self, raw: Any) -> List[Any]:
        """Convert raw payloads into domain models. Must not raise on bad rows."""
        ...

    def health_check(self) -> SourceHealth:
        """Report the adapter's current status without ingesting."""
        ...


class BaseSource:
    """Small shared base: config access, enablement and health reporting."""

    name = "base"
    authority = "SUPPLEMENTAL"

    def __init__(self, settings, enabled: bool = True):
        self.settings = settings or {}
        self.enabled = enabled
        self._last_error = ""
        self._last_reason = None

    def setting(self, key: str, default: Any = None) -> Any:
        return self.settings.get(key, default)

    def _health(self, status: str, checked_at: str, records: int = 0, message: str = "",
                reason=None, details=None) -> SourceHealth:
        return SourceHealth(
            name=self.name,
            status=status,
            authority=self.authority,
            checked_at=checked_at,
            records=records,
            message=message,
            reason=reason,
            details=details or {},
        )
