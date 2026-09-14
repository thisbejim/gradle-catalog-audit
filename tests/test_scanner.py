from __future__ import annotations

from pathlib import Path

from gradle_catalog_audit import Severity, audit_project
from gradle_catalog_audit.render import render_json, render_sarif, render_text

FIXTURES = Path(__file__).parent / "fixtures"


def codes(root: Path) -> list[str]:
    return [finding.code for finding in audit_project(root).findings]


def test_good_project_is_clean() -> None:
    report = audit_project(FIXTURES / "good")
    assert report.findings == []
    assert report.errors == 0
    assert report.warnings == 0


def test_bad_project_reports_contract_failures() -> None:
    report = audit_project(FIXTURES / "bad")
    assert report.errors >= 5
    assert {"CAT006", "CAT008", "CAT009", "CAT010", "CAT013"} <= set(codes(FIXTURES / "bad"))
    assert "CAT011" in codes(FIXTURES / "bad")
    assert any(item.severity is Severity.WARNING for item in report.findings)


def test_malformed_toml_is_a_single_readable_error() -> None:
    report = audit_project(FIXTURES / "malformed")
    assert len(report.findings) == 1
    assert report.findings[0].code == "CAT001"
    assert "invalid TOML" in report.findings[0].message


def test_explicit_catalog_path_and_relative_paths() -> None:
    report = audit_project(FIXTURES / "good", ["gradle/libs.versions.toml"])
    assert report.catalogs == ["gradle/libs.versions.toml"]
    assert report.build_files == ["app/build.gradle.kts", "settings.gradle.kts"]


def test_ignore_codes_removes_all_matching_findings() -> None:
    report = audit_project(FIXTURES / "bad", ignore=["CAT020", "CAT011"])
    assert all(item.code not in {"CAT020", "CAT011"} for item in report.findings)


def test_used_bundle_marks_member_library_as_used(tmp_path: Path) -> None:
    (tmp_path / "gradle").mkdir()
    (tmp_path / "gradle/libs.versions.toml").write_text(
        '[libraries]\nfoo = "a:b:1"\n[bundles]\nall = ["foo"]\n',
        encoding="utf-8",
    )
    (tmp_path / "build.gradle.kts").write_text(
        "dependencies { implementation(libs.bundles.all) }\n", encoding="utf-8"
    )
    assert audit_project(tmp_path).findings == []


def test_dead_library_does_not_keep_its_version_alive(tmp_path: Path) -> None:
    (tmp_path / "gradle").mkdir()
    (tmp_path / "gradle/libs.versions.toml").write_text(
        '[versions]\nold = "1.0"\n[libraries]\nunused = { module = "a:b", version.ref = "old" }\n',
        encoding="utf-8",
    )
    report = audit_project(tmp_path)
    messages = [item.message for item in report.findings if item.code == "CAT020"]
    assert any("version alias 'old'" in message for message in messages)


def test_dynamic_literal_known_alias_is_marked_used(tmp_path: Path) -> None:
    (tmp_path / "gradle").mkdir()
    (tmp_path / "gradle/libs.versions.toml").write_text(
        '[libraries]\nfoo = "a:b:1"\n', encoding="utf-8"
    )
    (tmp_path / "settings.gradle").write_text('def x = libs.findLibrary("foo")\n', encoding="utf-8")
    assert audit_project(tmp_path).findings == []


def test_unknown_dynamic_alias_is_warning_not_error(tmp_path: Path) -> None:
    (tmp_path / "gradle").mkdir()
    (tmp_path / "gradle/libs.versions.toml").write_text(
        '[libraries]\nfoo = "a:b:1"\n', encoding="utf-8"
    )
    (tmp_path / "build.gradle").write_text(
        'def x = libs.findLibrary("bar")\nimplementation(libs.foo)\n', encoding="utf-8"
    )
    report = audit_project(tmp_path)
    assert [(item.code, item.severity) for item in report.findings] == [
        ("CAT011", Severity.WARNING)
    ]


def test_dynamic_variable_lookup_is_a_note(tmp_path: Path) -> None:
    (tmp_path / "gradle").mkdir()
    (tmp_path / "gradle/libs.versions.toml").write_text(
        '[libraries]\nfoo = "a:b:1"\n', encoding="utf-8"
    )
    (tmp_path / "build.gradle").write_text(
        "def alias = project.name\ndef x = libs.findLibrary(alias)\nimplementation(libs.foo)\n",
        encoding="utf-8",
    )
    report = audit_project(tmp_path)
    assert [(item.code, item.severity) for item in report.findings] == [("CAT014", Severity.NOTE)]


def test_catalog_name_is_derived_from_filename(tmp_path: Path) -> None:
    (tmp_path / "gradle").mkdir()
    (tmp_path / "gradle/tools.versions.toml").write_text(
        '[libraries]\nfoo = "a:b:1"\n', encoding="utf-8"
    )
    (tmp_path / "build.gradle.kts").write_text(
        "dependencies { implementation(tools.foo) }\n", encoding="utf-8"
    )
    assert audit_project(tmp_path).findings == []


def test_json_report_is_versioned() -> None:
    import json

    payload = json.loads(render_json(audit_project(FIXTURES / "good")))
    assert payload["schemaVersion"] == 1
    assert payload["summary"]["findings"] == 0


def test_sarif_report_has_expected_schema_and_results() -> None:
    import json

    payload = json.loads(render_sarif(audit_project(FIXTURES / "bad")))
    assert payload["version"] == "2.1.0"
    assert payload["runs"][0]["tool"]["driver"]["name"] == "gradle-catalog-audit"
    assert payload["runs"][0]["results"]


def test_text_report_mentions_hint_and_summary() -> None:
    text = render_text(audit_project(FIXTURES / "bad"))
    assert "Audited 1 catalog(s)" in text
    assert "CAT013" in text
    assert "hint:" in text
