from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
FIXTURES = ROOT / "tests/fixtures"


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "gradle_catalog_audit.cli", *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_cli_good_project_passes() -> None:
    result = run_cli(str(FIXTURES / "good"), "--strict")
    assert result.returncode == 0
    assert "No findings." in result.stdout


def test_cli_strict_turns_unused_warning_into_failure() -> None:
    ignored = "CAT005,CAT006,CAT008,CAT009,CAT010,CAT013,CAT011"
    result = run_cli(str(FIXTURES / "bad"), "--ignore", ignored)
    assert result.returncode == 0
    strict = run_cli(str(FIXTURES / "bad"), "--strict", "--ignore", ignored)
    assert strict.returncode == 1


def test_cli_json_and_sarif_are_parseable() -> None:
    import json

    json_result = run_cli(str(FIXTURES / "good"), "--format", "json")
    sarif_result = run_cli(str(FIXTURES / "good"), "--format", "sarif")
    assert json.loads(json_result.stdout)["schemaVersion"] == 1
    assert json.loads(sarif_result.stdout)["version"] == "2.1.0"


def test_cli_help_and_version() -> None:
    help_result = run_cli("--help")
    version_result = run_cli("--version")
    assert help_result.returncode == 0
    assert "Audit Gradle version-catalog" in help_result.stdout
    assert version_result.returncode == 0
    assert "gradle-catalog-audit 0.1.0" in version_result.stdout
