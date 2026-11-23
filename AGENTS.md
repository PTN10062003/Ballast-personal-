# Ballast: start here

The Ballast instructions are in the [`plugin`](plugin) folder of this repository.

Before starting a cleanup or weekly check, confirm the operator compared this checkout to the independently pinned fork source or authenticated release from outside this folder ([verification](SECURITY.md#verify-before-loading-ballast)). If verification is missing or failed, pause the run. After it passes, read [plugin/AGENTS.md](plugin/AGENTS.md) and follow it. Every file it names (`cleanup.md`,
`permissions.md`, `weekly.md`, `dashboard.md`, `steps/`, `catalog/`) is inside `plugin`, so "run cleanup.md"
means `plugin/cleanup.md` and "run weekly.md" means `plugin/weekly.md`.

Do not skip the integrity check or the two consent questions, and do not delete or stop anything without the
user's approval for that specific item.
