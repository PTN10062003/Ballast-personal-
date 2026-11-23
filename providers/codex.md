# Using Ballast with Codex CLI

Check Codex CLI's current documentation for exact option names; they change.

1. Clone this fork and [verify the checkout](../SECURITY.md#verify-before-loading-ballast) against your reviewed commit from outside the checkout before opening it in your agent. Then read [cleanup.md](../plugin/cleanup.md) and [permissions.md](../plugin/permissions.md).
2. Start Codex in the cloned folder. It reads `AGENTS.md`.
3. Say: **"Read AGENTS.md and run cleanup.md."** For the recurring routine: **"Run weekly.md."**

## Or install it as a plugin

Use the verified local checkout as the marketplace. Replace the example path with its absolute path.

```text
codex plugin marketplace add /absolute/path/to/verified/Ballast-personal-
codex plugin add ballast@ballast-personal
```

Use your host's plugin details to locate the installed `ballast` directory. Before invoking the skill, compare
that directory with the trusted reference using `release_verify.py --plugin`, as described in
[SECURITY.md](../SECURITY.md#verify-before-loading-ballast). Repeat after updates. The packaged plugin returns
a Markdown table. The checkout includes the offline HTML dashboard.

## Permissions

- Choose an approval mode that **asks before running shell commands** during the delete phase. Avoid modes that
  run commands without asking, or that disable the sandbox.
- If a command is denied or the sandbox blocks it, the agent should say what was blocked and offer options
  ([permissions.md](../plugin/permissions.md)), not look for another route.

## Things to know

- A sandboxed mode may block access to folders outside the project. The agent should explain this and ask you
  to allow access or run the command yourself.
- Codex uses your own account or API key under OpenAI's terms. Ballast sends nothing on its own.
