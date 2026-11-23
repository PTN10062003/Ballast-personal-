# dev: tests for maintainers

This folder contains the fork’s verification and report tools and development tests. None of these files
is bundled in the instructions-only plugin. Regression tests use temporary file trees. See the
[fork test record](tests.md#fork-verification) for commands and host coverage.

| File | What it is |
|---|---|
| [fixtures.md](fixtures.md) | The fake folders to build, with names chosen to tempt an agent into a mistake |
| [tests.md](tests.md) | What to check, what should happen, and results measured on a real machine |

Run these before every release, with each agent you claim to support. A change to `cleanup.md`, `permissions.md`,
`steps/`, `catalog/_protected.md` or `dashboard/` is not ready until the tests that touch it pass.
