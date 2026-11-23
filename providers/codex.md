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

## Reading the Codex reports

After verifying the checkout or installed plugin, name the host whose state you want to inspect.
For example, Windows Desktop and a CLI running in WSL can have different Codex homes. You can ask
for either report on its own. Both appear in chat after consent.

| Ask Ballast | How to read the answer |
|---|---|
| “Show how much space Codex uses on Windows.” | Read file counts and logical GiB per volume for active sessions, archived sessions, diagnostics and recognized databases. To include a backup, identify its dedicated folder. “At least” means Ballast measured part of a category. “Unknown” means it could not establish a size. These rows have no Clear action. |
| “Why does this project still appear in my Codex sidebar?” | Ballast compares saved project definitions and chat assignments locally. When a private, read-only native inventory is available, it includes active and archived chats. A **Desktop-only** result counts saved assignment records. It cannot establish whether those chats still exist or what another device currently displays. |

A project can be absent from the saved sidebar order while its chats still have valid assignments.
A missing folder alone is insufficient evidence for deletion. If the discrepancy appears on a phone,
check that device after refreshing. Only counts, sizes and coverage information appear in the diagnostic
output. [Storage categories](../plugin/catalog/codex-storage.md) · [Sidebar coverage](../plugin/catalog/codex-sidebar.md)

If you decide to remove a project from the sidebar or archive a chat, use the owning Codex host’s
native action. The separate `codex-local-cleanup` skill can help diagnose a failed action if you have
it installed. Archiving retains conversation history and carries no promised disk-space gain.

## Permissions

- Choose an approval mode that **asks before running shell commands** during the delete phase. Avoid modes that
  run commands without asking, or that disable the sandbox.
- If a command is denied or the sandbox blocks it, the agent should say what was blocked and offer options
  ([permissions.md](../plugin/permissions.md)), not look for another route.

## Things to know

- A sandboxed mode may block access to folders outside the project. The agent should explain this and ask you
  to allow access or run the command yourself.
- Codex uses your own account or API key under OpenAI's terms. Ballast sends nothing on its own.
