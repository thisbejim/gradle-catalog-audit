"""Offline parser and repository scanner for Gradle version catalogs."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from .model import AuditReport, Finding, Severity
from .toml_compat import load_toml

CATALOG_SECTIONS = ("versions", "libraries", "bundles", "plugins")
ALIAS_RE = re.compile(r"^[a-z][A-Za-z0-9_.-]*$")
SECTION_RE = re.compile(r"^\s*\[([^\]]+)\]")
ENTRY_RE = re.compile(r"^\s*([A-Za-z][A-Za-z0-9_.-]*)\s*=")
ACCESSOR_RE = re.compile(
    r"\b(?P<catalog>[A-Za-z][A-Za-z0-9_]*)\.(?P<chain>[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)"
)
DYNAMIC_RE = re.compile(
    r"\b(?P<catalog>[A-Za-z][A-Za-z0-9_]*)\s*\.\s*"
    r"(?P<method>find(?:Library|Plugin|Bundle)|get(?:Library|Plugin|Bundle|Version))"
    r"\s*\(\s*['\"](?P<alias>[A-Za-z][A-Za-z0-9_.-]*)['\"]"
)
DYNAMIC_SITE_RE = re.compile(
    r"\b(?P<catalog>[A-Za-z][A-Za-z0-9_]*)\s*\.\s*"
    r"(?P<method>find(?:Library|Plugin|Bundle)|get(?:Library|Plugin|Bundle|Version))"
    r"\s*\("
)
RESERVED_SEGMENTS = {"versions", "libraries", "bundles", "plugins", "extensions", "class"}
BUILD_SUFFIXES = {".gradle", ".gradle.kts"}
IGNORED_DIRS = {".git", ".gradle", "build", "out", ".idea", ".venv", "venv"}


def normalize_alias(alias: str) -> str:
    """Return the generated accessor path for a TOML alias."""

    return ".".join(part for part in re.split(r"[-_.]", alias) if part)


def _relative(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _line_for(lines: dict[tuple[str, str], int], section: str, alias: str) -> int | None:
    return lines.get((section, alias))


@dataclass(frozen=True, slots=True)
class Alias:
    section: str
    name: str
    normalized: str
    line: int | None


@dataclass(slots=True)
class Catalog:
    path: Path
    name: str
    data: dict[str, object]
    lines: dict[tuple[str, str], int]
    aliases: dict[tuple[str, str], Alias] = field(default_factory=dict)
    used: set[tuple[str, str]] = field(default_factory=set)


def _parse_line_map(text: str) -> dict[tuple[str, str], int]:
    section = ""
    result: dict[tuple[str, str], int] = {}
    for number, line in enumerate(text.splitlines(), 1):
        section_match = SECTION_RE.match(line)
        if section_match:
            section = section_match.group(1).strip()
            continue
        if section in CATALOG_SECTIONS:
            entry_match = ENTRY_RE.match(line)
            if entry_match:
                result[(section, entry_match.group(1))] = number
    return result


def _catalog_name(path: Path) -> str:
    stem = path.name
    if stem.endswith(".versions.toml"):
        return stem[: -len(".versions.toml")] or "libs"
    return path.stem


def _finding(
    code: str,
    severity: Severity,
    message: str,
    root: Path,
    path: Path,
    *,
    line: int | None = None,
    suggestion: str | None = None,
) -> Finding:
    return Finding(code, severity, message, _relative(root, path), line, suggestion=suggestion)


def _version_ref(value: object) -> str | None:
    """Read both TOML spellings of ``version.ref``."""

    if not isinstance(value, dict):
        return None
    direct = value.get("version.ref")
    if isinstance(direct, str):
        return direct
    nested = value.get("version")
    if isinstance(nested, dict):
        nested_ref = nested.get("ref")
        if isinstance(nested_ref, str):
            return nested_ref
    return None


def _section_label(section: str) -> str:
    return {
        "versions": "version",
        "libraries": "library",
        "bundles": "bundle",
        "plugins": "plugin",
    }[section]


def _iter_build_files(root: Path) -> list[Path]:
    result: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix not in {".gradle", ".kts"}:
            continue
        if not (path.name.endswith(".gradle") or path.name.endswith(".gradle.kts")):
            continue
        if any(part in IGNORED_DIRS for part in path.relative_to(root).parts):
            continue
        result.append(path)
    return sorted(result)


def _discover_catalogs(root: Path) -> list[Path]:
    conventional = root / "gradle"
    if conventional.is_dir():
        paths = sorted(conventional.glob("*.versions.toml"))
        if paths:
            return paths
    return sorted(
        path
        for path in root.rglob("*.versions.toml")
        if path.is_file() and not any(part in IGNORED_DIRS for part in path.relative_to(root).parts)
    )


def _load_catalog(root: Path, path: Path, findings: list[Finding]) -> Catalog | None:
    try:
        text = path.read_text(encoding="utf-8")
        data = load_toml(text)
    except (OSError, UnicodeError) as exc:
        findings.append(
            _finding(
                "CAT001",
                Severity.ERROR,
                f"cannot read version catalog: {exc}",
                root,
                path,
            )
        )
        return None
    except Exception as exc:  # TOMLDecodeError differs slightly across Python versions
        findings.append(_finding("CAT001", Severity.ERROR, f"invalid TOML: {exc}", root, path))
        return None
    return Catalog(path, _catalog_name(path), data, _parse_line_map(text))


def _validate_catalog(root: Path, catalog: Catalog, findings: list[Finding]) -> None:
    for section, raw in catalog.data.items():
        if section not in CATALOG_SECTIONS:
            findings.append(
                _finding(
                    "CAT002",
                    Severity.ERROR,
                    f"unsupported top-level catalog section [{section}]",
                    root,
                    catalog.path,
                )
            )
            continue
        if not isinstance(raw, dict):
            findings.append(
                _finding(
                    "CAT003",
                    Severity.ERROR,
                    f"catalog section [{section}] must be a table",
                    root,
                    catalog.path,
                )
            )
            continue
        for alias, value in raw.items():
            if not isinstance(alias, str):
                continue
            line = _line_for(catalog.lines, section, alias)
            if not ALIAS_RE.fullmatch(alias):
                findings.append(
                    _finding(
                        "CAT004",
                        Severity.ERROR,
                        f"invalid {section} alias {alias!r}; aliases must start with a "
                        "lowercase letter",
                        root,
                        catalog.path,
                        line=line,
                        suggestion="Use lowercase letters, digits, dots, dashes, or underscores.",
                    )
                )
            normalized = normalize_alias(alias)
            if normalized.split(".", 1)[0] in RESERVED_SEGMENTS:
                findings.append(
                    _finding(
                        "CAT005",
                        Severity.ERROR,
                        f"{section} alias {alias!r} creates a reserved accessor group",
                        root,
                        catalog.path,
                        line=line,
                        suggestion=(
                            "Rename the alias so its first accessor segment is not reserved "
                            "by Gradle."
                        ),
                    )
                )
            key = (section, normalized)
            previous = catalog.aliases.get(key)
            if previous is not None:
                findings.append(
                    _finding(
                        "CAT006",
                        Severity.ERROR,
                        f"aliases {previous.name!r} and {alias!r} collide as "
                        f"{catalog.name}.{normalized}",
                        root,
                        catalog.path,
                        line=line,
                        suggestion="Keep only one spelling for each generated accessor path.",
                    )
                )
            else:
                catalog.aliases[key] = Alias(section, alias, normalized, line)

            if section == "bundles" and not isinstance(value, list):
                findings.append(
                    _finding(
                        "CAT007",
                        Severity.ERROR,
                        f"bundle {alias!r} must be an array of library aliases",
                        root,
                        catalog.path,
                        line=line,
                    )
                )
            elif section in {"libraries", "plugins"} and not isinstance(value, (str, dict)):
                findings.append(
                    _finding(
                        "CAT008",
                        Severity.ERROR,
                        f"{_section_label(section)} {alias!r} must be a string or inline table",
                        root,
                        catalog.path,
                        line=line,
                    )
                )

    versions = catalog.data.get("versions")
    if not isinstance(versions, dict):
        versions = {}
    for section in ("libraries", "plugins"):
        entries = catalog.data.get(section)
        if not isinstance(entries, dict):
            continue
        for alias, value in entries.items():
            if not isinstance(value, dict):
                continue
            version_ref = _version_ref(value)
            if version_ref is not None and version_ref not in versions:
                findings.append(
                    _finding(
                        "CAT009",
                        Severity.ERROR,
                        f"{_section_label(section)} {alias!r} references missing version "
                        f"{version_ref!r}",
                        root,
                        catalog.path,
                        line=_line_for(catalog.lines, section, str(alias)),
                        suggestion="Define the version in [versions] or use an inline version.",
                    )
                )
    libraries = catalog.data.get("libraries")
    if not isinstance(libraries, dict):
        libraries = {}
    bundles = catalog.data.get("bundles")
    if isinstance(bundles, dict):
        for bundle, members in bundles.items():
            if not isinstance(members, list):
                continue
            for member in members:
                if not isinstance(member, str):
                    findings.append(
                        _finding(
                            "CAT010",
                            Severity.ERROR,
                            f"bundle {bundle!r} contains a non-string library alias",
                            root,
                            catalog.path,
                            line=_line_for(catalog.lines, "bundles", str(bundle)),
                        )
                    )
                elif member not in libraries:
                    findings.append(
                        _finding(
                            "CAT010",
                            Severity.ERROR,
                            f"bundle {bundle!r} references missing library {member!r}",
                            root,
                            catalog.path,
                            line=_line_for(catalog.lines, "bundles", str(bundle)),
                            suggestion=(
                                "Add the library alias to [libraries] or remove it from the bundle."
                            ),
                        )
                    )


def _mark_dynamic_usage(
    catalog: Catalog, text: str, path: Path, root: Path, findings: list[Finding]
) -> None:
    literal_sites: set[int] = set()
    for match in DYNAMIC_RE.finditer(text):
        if match.group("catalog") != catalog.name:
            continue
        literal_sites.add(match.start())
        alias = match.group("alias")
        method = match.group("method")
        section = {
            "findLibrary": "libraries",
            "getLibrary": "libraries",
            "findPlugin": "plugins",
            "getPlugin": "plugins",
            "findBundle": "bundles",
            "getBundle": "bundles",
            "getVersion": "versions",
        }[method]
        key = (section, normalize_alias(alias))
        if key in catalog.aliases:
            catalog.used.add(key)
        else:
            findings.append(
                _finding(
                    "CAT011",
                    Severity.WARNING,
                    f"dynamic {catalog.name}.{method} lookup names unknown alias {alias!r}",
                    root,
                    path,
                    line=text.count("\n", 0, match.start()) + 1,
                    suggestion=(
                        "Use a generated accessor when possible so typos are checked statically."
                    ),
                )
            )
    for match in DYNAMIC_SITE_RE.finditer(text):
        if match.group("catalog") != catalog.name or match.start() in literal_sites:
            continue
        findings.append(
            _finding(
                "CAT014",
                Severity.NOTE,
                f"dynamic {catalog.name}.{match.group('method')} lookup cannot be "
                "resolved statically",
                root,
                path,
                line=text.count("\n", 0, match.start()) + 1,
                suggestion=(
                    "Prefer a literal alias or review this lookup when catalog entries change."
                ),
            )
        )


def _scan_usage(
    root: Path, catalogs: list[Catalog], build_files: list[Path], findings: list[Finding]
) -> None:
    for path in build_files:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            findings.append(
                _finding("CAT012", Severity.ERROR, f"cannot read build script: {exc}", root, path)
            )
            continue
        for catalog in catalogs:
            _mark_dynamic_usage(catalog, text, path, root, findings)
            accessors = {key: alias for key, alias in catalog.aliases.items()}
            for match in ACCESSOR_RE.finditer(text):
                if match.group("catalog") != catalog.name:
                    continue
                segments = match.group("chain").split(".")
                if segments[0] in {
                    "findLibrary",
                    "findPlugin",
                    "findBundle",
                    "getLibrary",
                    "getPlugin",
                    "getBundle",
                    "getVersion",
                } and text[match.end() :].lstrip().startswith("("):
                    continue
                section = "libraries"
                if segments[0] in {"plugins", "bundles", "versions"}:
                    section = segments.pop(0)
                if not segments:
                    continue
                found: tuple[str, str] | None = None
                for end in range(len(segments), 0, -1):
                    candidate = (section, ".".join(segments[:end]))
                    if candidate in accessors:
                        found = candidate
                        break
                if found is not None:
                    catalog.used.add(found)
                    continue
                # Do not flag a bare catalog reference such as `libs` in prose. A
                # dotted accessor with no known prefix is actionable and usually a typo.
                findings.append(
                    _finding(
                        "CAT013",
                        Severity.ERROR,
                        f"unknown {_section_label(section)} accessor "
                        f"{catalog.name}.{'.'.join(segments)}",
                        root,
                        path,
                        line=text.count("\n", 0, match.start()) + 1,
                        suggestion="Check the alias spelling in the matching version catalog.",
                    )
                )


def _emit_unused(root: Path, catalog: Catalog, findings: list[Finding]) -> None:
    # A used bundle makes each of its members an effective library use.
    bundles = catalog.data.get("bundles")
    if isinstance(bundles, dict):
        changed = True
        while changed:
            changed = False
            for bundle, members in bundles.items():
                bundle_key = ("bundles", normalize_alias(str(bundle)))
                if bundle_key not in catalog.used or not isinstance(members, list):
                    continue
                for member in members:
                    if isinstance(member, str):
                        key = ("libraries", normalize_alias(member))
                        if key in catalog.aliases and key not in catalog.used:
                            catalog.used.add(key)
                            changed = True
    # Version references only count as consumed when their owning library/plugin
    # is consumed by a build script (a dead alias must not keep a version alive).
    for section in ("libraries", "plugins"):
        entries = catalog.data.get(section)
        if not isinstance(entries, dict):
            continue
        for alias, value in entries.items():
            key = (section, normalize_alias(str(alias)))
            if key not in catalog.used:
                continue
            version_ref = _version_ref(value)
            if version_ref is not None:
                version_key = ("versions", normalize_alias(version_ref))
                if version_key in catalog.aliases:
                    catalog.used.add(version_key)
    for key, alias in sorted(catalog.aliases.items()):
        if key in catalog.used:
            continue
        # A version is intentionally allowed to be kept for programmatic catalog
        # consumers; this is a warning, never an error.
        section_label = _section_label(alias.section)
        findings.append(
            _finding(
                "CAT020",
                Severity.WARNING,
                f"unused {section_label} alias {alias.name!r} "
                f"(accessor {catalog.name}.{alias.normalized})",
                root,
                catalog.path,
                line=alias.line,
                suggestion=(
                    "Remove it, reference it from a build script, or ignore CAT020 for "
                    "shared catalogs."
                ),
            )
        )


def audit_project(
    root: str | Path = ".",
    catalog_paths: Iterable[str | Path] | None = None,
    *,
    ignore: Iterable[str] = (),
) -> AuditReport:
    """Audit version catalogs and Gradle build-script accessors under *root*.

    The function never invokes Gradle, resolves dependencies, accesses the network,
    or modifies project files.
    """

    root_path = Path(root).resolve()
    selected = (
        [Path(item) for item in catalog_paths]
        if catalog_paths is not None
        else _discover_catalogs(root_path)
    )
    selected = [item if item.is_absolute() else root_path / item for item in selected]
    selected = sorted(dict.fromkeys(path.resolve() for path in selected))
    findings: list[Finding] = []
    catalogs: list[Catalog] = []
    for path in selected:
        catalog = _load_catalog(root_path, path, findings)
        if catalog is not None:
            catalogs.append(catalog)

    names: dict[str, Catalog] = {}
    for catalog in catalogs:
        previous = names.get(catalog.name)
        if previous is not None:
            findings.append(
                _finding(
                    "CAT021",
                    Severity.ERROR,
                    f"catalog name {catalog.name!r} is used by both "
                    f"{_relative(root_path, previous.path)} and "
                    f"{_relative(root_path, catalog.path)}",
                    root_path,
                    catalog.path,
                    suggestion=(
                        "Rename one file or pass explicit catalog paths with distinct "
                        ".versions.toml names."
                    ),
                )
            )
        names[catalog.name] = catalog
        _validate_catalog(root_path, catalog, findings)

    build_files = _iter_build_files(root_path)
    _scan_usage(root_path, catalogs, build_files, findings)
    for catalog in catalogs:
        _emit_unused(root_path, catalog, findings)

    ignored = {code.strip() for code in ignore if code.strip()}
    if ignored:
        findings = [finding for finding in findings if finding.code not in ignored]
    findings.sort(key=lambda item: (item.path, item.line or 0, item.code, item.message))
    return AuditReport(
        _relative(root_path, root_path) or ".",
        findings,
        [_relative(root_path, catalog.path) for catalog in catalogs],
        [_relative(root_path, path) for path in build_files],
    )
