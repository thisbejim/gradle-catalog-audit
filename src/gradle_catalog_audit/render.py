"""Deterministic report renderers."""

from __future__ import annotations

import json
from typing import Any

from .model import AuditReport, Finding, Severity


def _summary(report: AuditReport) -> str:
    return (
        f"Audited {len(report.catalogs)} catalog(s) and {len(report.build_files)} build script(s): "
        f"{report.errors} error(s), {report.warnings} warning(s)."
    )


def render_text(report: AuditReport) -> str:
    """Render compact human-readable output."""

    lines = [_summary(report)]
    if not report.findings:
        lines.append("No findings.")
        return "\n".join(lines)
    for finding in report.findings:
        location = finding.path
        if finding.line is not None:
            location += f":{finding.line}"
        lines.append(
            f"{finding.severity.value.upper():7} {finding.code} {location} — {finding.message}"
        )
        if finding.suggestion:
            lines.append(f"         hint: {finding.suggestion}")
    return "\n".join(lines)


def render_json(report: AuditReport) -> str:
    """Render the versioned JSON report."""

    return json.dumps(report.as_dict(), indent=2, sort_keys=True) + "\n"


def _rule_descriptions(findings: list[Finding]) -> list[dict[str, Any]]:
    rules: dict[str, dict[str, Any]] = {}
    for finding in findings:
        if finding.code in rules:
            continue
        level = {Severity.ERROR: "error", Severity.WARNING: "warning", Severity.NOTE: "note"}[
            finding.severity
        ]
        rules[finding.code] = {
            "id": finding.code,
            "shortDescription": {"text": finding.code},
            "help": {"text": finding.message},
            "defaultConfiguration": {"level": level},
        }
    return [rules[key] for key in sorted(rules)]


def render_sarif(report: AuditReport) -> str:
    """Render SARIF 2.1.0 for code-scanning or CI annotations."""

    results: list[dict[str, Any]] = []
    for finding in report.findings:
        result: dict[str, Any] = {
            "ruleId": finding.code,
            "level": {Severity.ERROR: "error", Severity.WARNING: "warning", Severity.NOTE: "note"}[
                finding.severity
            ],
            "message": {"text": finding.message},
            "locations": [
                {
                    "physicalLocation": {
                        "artifactLocation": {"uri": finding.path},
                        **(
                            {"region": {"startLine": finding.line}}
                            if finding.line is not None
                            else {}
                        ),
                    }
                }
            ],
        }
        if finding.suggestion:
            result["properties"] = {"suggestion": finding.suggestion}
        results.append(result)
    document = {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "gradle-catalog-audit",
                        "rules": _rule_descriptions(report.findings),
                    }
                },
                "results": results,
            }
        ],
    }
    return json.dumps(document, indent=2, sort_keys=True) + "\n"
