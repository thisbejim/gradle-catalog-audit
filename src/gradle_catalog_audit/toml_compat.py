"""Small TOML compatibility shim."""

from __future__ import annotations

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.11+ is supported
    tomllib = None  # type: ignore[assignment]


def load_toml(text: str) -> dict[str, object]:
    """Parse TOML using the Python standard library."""

    if tomllib is None:  # pragma: no cover
        raise RuntimeError("Python 3.11 or newer is required")
    value = tomllib.loads(text)
    if not isinstance(value, dict):  # pragma: no cover - tomllib guarantees this
        raise ValueError("TOML document must be a table")
    return value
