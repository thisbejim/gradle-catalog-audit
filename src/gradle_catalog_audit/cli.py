"""Command-line interface for gradle-catalog-audit."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .render import render_json, render_sarif, render_text
from .scanner import audit_project


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gradle-catalog-audit",
        description="Audit Gradle version-catalog definitions and build-script usage offline.",
    )
    parser.add_argument(
        "root", nargs="?", default=".", help="project root to scan (default: current directory)"
    )
    parser.add_argument(
        "--catalog",
        action="append",
        dest="catalogs",
        metavar="PATH",
        help=(
            "catalog path relative to root; repeat to scan multiple catalogs "
            "(default: gradle/*.versions.toml)"
        ),
    )
    parser.add_argument(
        "--format",
        choices=("text", "json", "sarif"),
        default="text",
        help="report format (default: text)",
    )
    parser.add_argument(
        "--strict", action="store_true", help="exit 1 for warnings as well as errors"
    )
    parser.add_argument(
        "--ignore",
        action="append",
        default=[],
        metavar="CODE",
        help="ignore a finding code; repeat or use comma-separated codes",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    ignores = [code for item in args.ignore for code in item.split(",")]
    report = audit_project(Path(args.root), args.catalogs, ignore=ignores)
    if args.format == "json":
        output = render_json(report)
    elif args.format == "sarif":
        output = render_sarif(report)
    else:
        output = render_text(report) + "\n"
    sys.stdout.write(output)
    if report.errors:
        return 1
    if args.strict and report.warnings:
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
