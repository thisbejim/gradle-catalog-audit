# Security

`gradle-catalog-audit` reads TOML and Gradle source files as untrusted text. It
does not execute Gradle, evaluate Groovy/Kotlin, invoke shells, access the network,
read environment credentials, or modify the scanned repository. Reports include
aliases and paths but never dependency secrets or file contents.

If you find a security issue, please avoid posting sensitive project contents in a
public issue. Contact the maintainer through GitHub and include a minimal
reproduction when possible.
