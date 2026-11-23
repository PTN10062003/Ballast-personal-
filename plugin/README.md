# Ballast

> Not legal advice. Not affiliated with, or endorsed by, any AI provider.

Ballast is a set of plain-text instructions that your AI agent follows to find and clear the disk and memory
leftovers that AI tools leave behind: Claude Code and Claude desktop (chat and Cowork), Codex, Gemini, Antigravity,
local models (their files on disk, and the GPU memory they keep loaded), MCP servers, headless browsers, and the
scratch projects agents create.

This folder is the whole plugin. It holds Markdown instructions, a catalog of known leftovers, one skill, a
manifest for each agent that installs it, and an icon. **There is no program, script, MCP server or hook in it, and it fetches nothing from the
web.** Your agent reads the instructions and uses its own tools, behind its own permission prompts.

## What it does

1. **Confirms the installation was verified**, discloses which metadata reaches the AI provider, and asks two separate consent questions before scanning.
2. **Scans, read-only.** It measures known AI leftovers, your Temp folder and the Recycle Bin, browser and Office
   caches, large unknown folders, and the memory and GPU memory held by leftover processes. It reads names, sizes
   and dates. The optional sidebar check compares project and chat metadata locally and reports counts.
3. **Sorts what it found into tiers** (Green, Yellow, Grey, Red) after eight checks per item, and shows you a
   table in the chat.
4. **You choose** what to clear. It then **asks again, per item, with the full path**, before anything is deleted.
5. **Deletes only what you approved**, to the Recycle Bin where that really works, and reports the measured result.

It never deletes personal files, backups, credentials, browser profiles, git history or AI memory files, and it
never works around your agent's permission prompts.

## How to use it

Use the fork marketplace `ballast-personal` from a verified checkout of
[PTN10062003/Ballast-personal-](https://github.com/PTN10062003/Ballast-personal-).
Select `ballast@ballast-personal` in your host. Before invocation compare the installed folder with the
trusted reference using the fork's [verification procedure](https://github.com/PTN10062003/Ballast-personal-/blob/main/SECURITY.md#verify-before-loading-ballast).
Keep the reference to recheck later sessions and updates.

Then run the `ballast` skill (`/ballast:ballast` in Claude Code), or just ask:

- "I'm low on disk space. Find what my AI tools have left behind."
- "Show my Codex storage totals and diagnose the sidebar." This optional
  [read-only report](catalog/codex-storage.md) summarizes counts and sizes in chat.
- "My laptop is struggling. What is holding memory and GPU memory right now?"
- "Run the weekly Ballast check and show me what has grown since last time."

For deletions, use a mode in which your agent asks you before it runs shell commands.

## What this install does not include

The cloned repository also has a static dashboard page that shows the same results in your browser. A plugin
install has no page, so you get the results as a table in the chat. To use the page, clone the repository:
<https://github.com/PTN10062003/Ballast-personal->.

## Your data

Ballast collects nothing and has no servers. Your agent reads folder names, paths, sizes and dates on your
computer, and whatever your agent reads reaches your AI provider under your own account. Details:
[privacy](https://github.com/PTN10062003/Ballast-personal-/blob/main/PRIVACY.md) ·
[safety](https://github.com/PTN10062003/Ballast-personal-/blob/main/SAFETY.md) ·
[security](https://github.com/PTN10062003/Ballast-personal-/blob/main/SECURITY.md).

## Status and support

Windows 11 is the first supported system. macOS and Linux rows are starters that have not been confirmed on a
real machine. Questions and bugs: <https://github.com/PTN10062003/Ballast-personal-/issues>.

Provided "as is", without warranty. Back up what matters before you clear anything.
[Apache License 2.0](LICENSE). See [NOTICE](NOTICE).
