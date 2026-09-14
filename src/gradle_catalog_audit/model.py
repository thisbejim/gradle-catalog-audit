"""Public data model for catalog audit findings."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class Severity(StrEnum):
    """Finding severity used by text, JSON, and SARIF renderers."""

    ERROR = "error"
    WARNING = "warning"
    NOTE = "note"


@dataclass(frozen=True, slots=True)
class Finding:
    """One deterministic, source-located audit result."""

    code: str
    severity: Severity
    message: str
    path: str
    line: int | None = None
    column: int | None = None
    suggestion: str | None = None

    def as_dict(self) -> dict[str, Any]:
        """Return a stable JSON-compatible representation."""

        result: dict[str, Any] = {
            "code": self.code,
            "severity": self.severity.value,
            "message": self.message,
            "path": self.path,
        }
        if self.line is not None:
            result["line"] = self.line
        if self.column is not None:
            result["column"] = self.column
        if self.suggestion is not None:
            result["suggestion"] = self.suggestion
        return result


@dataclass(slots=True)
class AuditReport:
    """All findings from one project audit."""

    root: str
    findings: list[Finding] = field(default_factory=list)
    catalogs: list[str] = field(default_factory=list)
    build_files: list[str] = field(default_factory=list)

    @property
    def errors(self) -> int:
        return sum(item.severity is Severity.ERROR for item in self.findings)

    @property
    def warnings(self) -> int:
        return sum(item.severity is Severity.WARNING for item in self.findings)

    def as_dict(self) -> dict[str, Any]:
        """Return the versioned JSON document."""

        return {
            "schemaVersion": 1,
            "root": self.root,
            "summary": {
                "catalogs": len(self.catalogs),
                "buildFiles": len(self.build_files),
                "findings": len(self.findings),
                "errors": self.errors,
                "warnings": self.warnings,
            },
            "findings": [item.as_dict() for item in self.findings],
        }
