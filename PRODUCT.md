# Product specification

## Target user

Android, Kotlin, JVM, and multiplatform teams that keep dependencies and plugin
versions in one or more Gradle version catalogs. The primary user is a developer
reviewing a dependency change or a CI maintainer who wants a fast repository gate.

## Problem

`libs.versions.toml` is a second API surface in a Gradle build. Gradle generates
accessors from catalog aliases, but a catalog can still accumulate dead aliases,
stale versions, bundle members that no longer exist, or build-script typos that
are difficult to diagnose in large multi-module repositories. Unused variables are
ignored by Gradle, so a green build does not mean the catalog is coherent.

## Current workaround and gap

Teams rely on IDE inspections, `grep`, or a Gradle invocation. IDE inspections are
not consistently available in headless CI and have known false-positive reports;
formatting/update plugins focus on TOML style or dependency updates rather than a
repository-wide, offline usage contract. A lightweight scanner can give a stable,
reviewable CI result without starting Gradle or resolving dependencies.

## Core use case

```text
gradle-catalog-audit . --strict
```

Discover `gradle/*.versions.toml`, scan all `build.gradle(.kts)` and
`settings.gradle(.kts)` files, and report invalid aliases, generated-accessor
collisions, missing version references, missing bundle libraries, unknown
accessors, dynamic lookups, and unused entries.

## Non-goals

* Dependency resolution, version freshness, vulnerability scanning, or license analysis.
* Evaluating arbitrary Groovy/Kotlin code or executing Gradle.
* Proving that a dynamically constructed accessor is used.
* Rewriting catalogs or build scripts.

## Interface and outputs

The CLI accepts a project root, repeated explicit catalog paths, ignored rule codes,
and `--strict`. Text is optimized for humans; versioned JSON and SARIF 2.1.0 are
stable for automation. Exit status is 1 for errors, or for warnings in strict mode.

## Inputs and behavior

Catalogs are TOML files. Build scripts are treated as untrusted text and are never
executed. Generated accessors are matched conservatively; dynamic
`findLibrary("alias")`-style calls are recognized when the alias is a literal and
otherwise produce a warning. No network, credentials, Gradle daemon, or project
write is involved.

## Supported environments

Python 3.11–3.14 on macOS, Linux, and Windows. The package has no runtime
dependencies and works in a clean checkout or via `uvx`/`pip`.

## Architecture and validation

The implementation has a small TOML model, a repository scanner, and deterministic
renderers. Tests cover valid and malformed catalogs, alias normalization and
collisions, bundles, version references, unknown and dynamic accessors, nested
modules, ignored rules, strict exits, JSON, and SARIF. Ruff, mypy, build, and a
clean wheel smoke test run in CI.

## Why it deserves to exist

This is a headless, offline contract check for the seam between a catalog and all
of the build scripts that consume it. It complements Gradle's own syntax checks,
IDE inspections, and dependency update tools by answering one focused question:
“Do the aliases declared in this repository still match the aliases its scripts
use?”
