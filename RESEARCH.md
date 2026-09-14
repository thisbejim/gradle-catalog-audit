# Opportunity research

## Candidate screen

| Candidate | Pain | Demand | Existing coverage | Decision |
| --- | ---: | ---: | --- | --- |
| Version-catalog usage/alias audit | 8 | 8 | IDE-only inspection, style/update plugins | **Selected** |
| Makefile dependency graph lint | 7 | 7 | `checkmake` is mature and active | Rejected |
| OpenTelemetry config lint | 7 | 7 | Official schema and validator already exist | Rejected |
| Go `//go:embed` asset coverage | 6 | 5 | Compiler catches missing patterns; remaining policy is project-specific | Rejected |

## Evidence for the selected problem

* Gradle's current documentation describes catalogs as generated accessors such as
  `libs.groovy.core`, notes that aliases are normalized into accessor groups, and
  documents recurring failures including accessor clashes and undefined aliases.
* Android's dependency-resolution documentation explicitly says unused variables in
  a version catalog are ignored. A stale entry therefore has no build-time signal.
* JetBrains ships an `UnusedVersionCatalogEntry` inspection, showing the job is
  concrete, but the long-running IDEA-316453 report records false “unused” warnings
  for both libraries and versions in real multi-module projects and asks for better
  reverse usage tracking.
* A Kotlin Slack discussion asks whether unused catalog entries can be found and
  describes a home-grown script that parses TOML and build files. That convergence
  is evidence that teams reinvent the same repository scan.
* The maintained `version-catalog-linter-gradle-plugin` is a formatter/style checker,
  while the `version-catalog-update-plugin` is an updater that may remove unused
  versions as part of an update run. Neither is a small, dependency-free, read-only
  CI audit of build-script references and typoed accessors.

## Current alternatives

* **Gradle itself:** catches malformed TOML and invalid generated accessors during a
  build, but does not report unused catalog entries and requires configuring/running
  the full build.
* **IntelliJ/Android Studio inspection:** useful interactively, but not a portable
  repository gate and historically prone to false positives around Kotlin DSL and
  `get()` usage.
* **Version catalog linter plugin:** checks formatting and ordering; it does not
  model every consuming build script.
* **Version catalog update plugin:** updates coordinates and can warn/remove unused
  versions, but it is a Gradle plugin with a different goal and cannot give a
  deterministic, no-resolution report for every alias typo.

## Search language

Likely high-intent searches include “Gradle unused version catalog entries”,
“libs.versions.toml alias typo”, “Gradle catalog CI lint”, “find unused Gradle
dependencies aliases”, and “version catalog bundle missing library”.

## Final challenge

Choose this repository when a team wants a fast, offline check that can run before
Gradle configuration, covers every module in one command, and produces JSON/SARIF
for CI. That is materially different from an IDE inspection or a formatter.
