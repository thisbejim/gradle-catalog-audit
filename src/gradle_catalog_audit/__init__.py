"""Static auditing for Gradle version catalogs."""

from .model import AuditReport, Finding, Severity
from .scanner import audit_project

__all__ = ["AuditReport", "Finding", "Severity", "audit_project"]
__version__ = "0.1.0"
