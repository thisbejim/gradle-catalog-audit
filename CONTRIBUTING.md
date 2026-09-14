# Contributing

1. Create a virtual environment with Python 3.11 or newer.
2. Install development tools with `uv sync --extra dev`.
3. Run `uv run pytest`, `uv run ruff check .`, and `uv run mypy`.
4. Keep findings deterministic and preserve the offline/read-only contract.

Please include a focused fixture and regression test for new rules. Do not add
network access, dependency resolution, telemetry, or commands that execute a
user's Gradle build.
