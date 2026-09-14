# gradle-catalog-audit

Offline CI lint for Gradle version catalogs and the build scripts that consume them.

Gradle's `libs.versions.toml` exposes type-safe dependency accessors, but a catalog can
quietly drift: unused aliases are ignored, a bundle can name a removed library, or a
large multi-module build can use a misspelled accessor. `gradle-catalog-audit` checks
that seam in one fast, read-only command—without starting Gradle or resolving a
single dependency.

## Quick start

```console
$ uvx --from git+https://github.com/thisbejim/gradle-catalog-audit.git gradle-catalog-audit . --strict
Audited 1 catalog(s) and 4 build script(s): 0 error(s), 0 warning(s).
No findings.
```

Or install the attached wheel directly from the release:

```console
python -m pip install https://github.com/thisbejim/gradle-catalog-audit/releases/download/v0.1.0/gradle_catalog_audit-0.1.0-py3-none-any.whl
gradle-catalog-audit .
```

The scanner discovers `gradle/*.versions.toml`, then checks every
`build.gradle`, `build.gradle.kts`, `settings.gradle`, and `settings.gradle.kts`
under the project root. It never executes those files or contacts a service.

## What it catches

* invalid aliases and generated-accessor collisions (`foo-bar` vs `foo_bar`);
* reserved accessor groups and malformed catalog section values;
* libraries/plugins that reference a missing `[versions]` entry;
* bundles that contain missing or non-string library aliases;
* unknown `libs.*`, `libs.plugins.*`, `libs.bundles.*`, and `libs.versions.*` accessors;
* literal `findLibrary`/`findPlugin`/`findBundle` lookups that name an unknown alias;
* unused libraries, plugins, bundles, and versions;
* dynamic lookup sites that cannot be proven statically.

Unused entries are warnings because published catalogs and convention plugins may be
consumed outside the checkout. `--strict` turns warnings into a CI failure.

## A useful failure

Given this catalog:

```toml
[versions]
kotlin = "2.0.21"

[libraries]
kotlin-stdlib = { module = "org.jetbrains.kotlin:kotlin-stdlib", version.ref = "kotlin" }

[bundles]
test = ["missing-library"]
```

and `app/build.gradle.kts` containing `implementation(libs.kotlin.stdlbi)`, the
audit points to both mistakes before a dependency resolution step:

```text
ERROR   CAT010 gradle/libs.versions.toml:8 — bundle 'test' references missing library 'missing-library'
ERROR   CAT013 app/build.gradle.kts:12 — unknown library accessor libs.kotlin.stdlbi
         hint: Check the alias spelling in the matching version catalog.
```

## Reports and CI

```console
# Explicit catalogs (useful for non-standard layouts)
gradle-catalog-audit . --catalog gradle/libs.versions.toml --catalog gradle/tools.versions.toml

# Machine-readable output
gradle-catalog-audit . --format json > catalog-audit.json
gradle-catalog-audit . --format sarif > catalog-audit.sarif

# Ignore a known shared-catalog warning
gradle-catalog-audit . --ignore CAT020
```

Exit status is `1` for errors. Add `--strict` to fail on warnings too. Rule codes
are stable (`CAT001`–`CAT021`) so ignores can be reviewed in code review.

## Why this instead of the usual options?

Gradle remains the authority for evaluating a build, and IDE inspections are useful
while editing. This tool is deliberately narrower: it is a dependency-free,
headless repository check that can run in seconds before Gradle configuration. It
also reports the cross-file contract (including dead entries and bundle membership)
that formatters and dependency update plugins do not model.

## Scope and limitations

The scanner understands standard TOML version catalogs and generated accessor syntax.
It does not evaluate arbitrary Groovy/Kotlin, resolve remote catalogs, inspect
dependencies actually selected by Gradle, or prove dynamically assembled alias
strings. Dynamic sites are called out so a team can review or ignore them. The tool
is read-only, offline, and has no telemetry.

## Development

```console
uv sync --extra dev
uv run pytest
uv run ruff check .
uv run mypy
uv build
```

Supported Python versions: 3.11–3.14 on macOS, Linux, and Windows.

## License

MIT © 2026 thisbejim
