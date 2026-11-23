# Using Ballast with Claude Code

Check Claude Code's current documentation for exact option names; they change.

1. Clone this fork and [verify the checkout](../SECURITY.md#verify-before-loading-ballast) against your reviewed commit from outside the checkout before opening it in your agent. Then read [cleanup.md](../plugin/cleanup.md) and [permissions.md](../plugin/permissions.md).
2. Open Claude Code in the cloned folder. It reads `CLAUDE.md`, which points to `AGENTS.md`, which sends it to
   the instructions in the `plugin` folder.
3. Say: **"Read AGENTS.md and run cleanup.md."** For the recurring routine: **"Run weekly.md."**

## Or install it as a plugin

Use the verified local checkout as the marketplace. Replace the example path with its absolute path.

```text
/plugin marketplace add /absolute/path/to/verified/Ballast-personal-
/plugin install ballast@ballast-personal
```

Use your host's plugin details to locate the installed `ballast` directory. Before invoking the skill, compare
that directory with the trusted reference using `release_verify.py --plugin`, as described in
[SECURITY.md](../SECURITY.md#verify-before-loading-ballast). Repeat after updates. The packaged plugin returns
a Markdown table. The checkout includes the offline HTML dashboard.

## Permissions

- During scanning, read-only commands are fine to allow.
- **During deletion, use a mode that prompts you for shell commands.** Do not use options that skip permission
  prompts (for example the flag named `--dangerously-skip-permissions`) or modes that auto-approve commands.
- If a command is denied, the agent should say exactly what was denied and offer options
  ([permissions.md](../plugin/permissions.md)), not look for another route to the same effect.

## Things to know

- The agent is told to avoid your own running Claude Code sessions. Check the process IDs it proposes to stop.
- Run it from a separate window from the work you care about, so closing apps does not interrupt it.
