# Claims register

Every public claim in this repo must map to something that enforces or proves it. Before a release, a maintainer
walks this table. If a claim has no enforcement, remove the claim or mark it "planned".

| Claim (where made) | Enforced by | How to check |
|---|---|---|
| If the agent is unsure it asks; it never decides for the user (README, AGENTS) | cleanup.md H0; permissions.md | Read H0 and the approval request format |
| Nothing is deleted without approval for that item (README, SAFETY) | cleanup.md H0, H1, H9; permissions.md; steps/06 | Run the fixtures in `dev/` (planned). Read steps/06 |
| Personal files, backups, credentials, browser profiles and memory files are never deleted (README) | catalog/_protected.md; cleanup.md H3; steps/04 rules 1 and 2 | Check no catalog row's path matches a protected pattern |
| "Ballast collects nothing" (PRIVACY) | The repo has no servers; the dashboard page has a Content-Security-Policy with no network access | Search the repo for any URL the agent or page is told to fetch or post to |
| The shipped plugin contains instructions, JSON metadata and an icon | Package allowlist and equality to the plugin subtree | Run `dev/release_tests.py` against both candidate ZIPs |
| Installations match the selected fork source or release | External verifier compares installed bytes with an independently obtained reference ZIP before invocation | Exercise both routes in `dev/release_tests.py` and the host smoke checklist |
| The dashboard page cannot delete anything and runs no network requests (README, dashboard.md) | The page's code and its Content-Security-Policy | Open it and read it; run the hostile-data tests: injected markup, script tags, text-direction characters, invalid tier, missing data |
| Red items cannot be selected, whatever the data says (dashboard.md) | The page forces Grey and Red to "Not offered" and gives them no Clear control | Feed it a Red item marked `Permanent` and confirm there is no radio |
| Never works around the permission system (README) | cleanup.md H7; permissions.md "never" list | Read permissions.md; test with a denied command |
| Never just says "I can't" (README) | permissions.md blocker table | Every blocker row offers options and asks for the permission needed |
| Recycle Bin or Trash first where it really works (README) | cleanup.md H10; steps/06 section 5 | Read steps/06; the log must say what actually happened |
| File classification uses filesystem metadata. An explicitly requested Codex diagnosis may also compare project and chat metadata locally and return aggregate results. | [Privacy rules](../PRIVACY.md), [storage probe](../plugin/catalog/codex-storage.md), [sidebar probe](../plugin/catalog/codex-sidebar.md) | Run `python -B dev/codex_diagnosis_tests.py -v` for the 25-chat assignment regression, aggregate output, pagination and incomplete coverage. |
| Items are "classified", never promised "safe" or "faster" (README) | cleanup.md H11 | Search the repo for banned words (below) |
| Rows are marked `active` only after confirmation (catalog) | catalog/README.md Status; SOURCES.md | Each `active` row has a Verified line |
| Instruction changes have designated reviewers | [.github/CODEOWNERS](../.github/CODEOWNERS) names the fork owner | Check current fork settings for any required review rules |
| Every release has a SHA-256 checksum file and a build attestation (SECURITY) | [.github/workflows/release.yml](../.github/workflows/release.yml), actions pinned to commit SHAs | `gh release view <tag>` lists the zip and `SHA256SUMS`; `gh attestation verify <zip> --repo PTN10062003/Ballast-personal-` passes |
| macOS and Linux rows (README, catalog) | catalog/macos.md and catalog/linux.md say every row is `planned` and Grey because none was observed | Check no row there is Yellow or Green or `active` |
| Graphics memory (VRAM) is read, never changed, and only measured numbers are shown (README, catalog/gpu-memory.md) | gpu-memory.md rules; cleanup.md H0, H13; the page hides the graphics line when numbers are missing | Read gpu-memory.md; run dev/tests.md D5; confirm no command there stops a process or resets a driver without approval |
| Temp, the Recycle Bin and browser caches are covered with the same ask-first rules; the Windows Installer cache is shown but never offered (README, catalog) | catalog/temp-and-recycle-bin.md (group rule, two-step Bin emptying); catalog/windows-and-app-caches.md; _protected.md; steps/06 | Read those files; C10 to C13 in dev/tests.md. Emptying the Recycle Bin and deleting Temp through Ballast are **not yet tested** (A12, A13) |
| The safety tests are written down with real results (dev) | [dev/tests.md](../dev/tests.md) | Each "Result" is either a measured outcome with a date and machine, or "Not yet run" |
| Checkout integrity covers all shipped content | Read and compare file names and hashes against the independently pinned source archive, without invoking repository-configured helpers | See [SECURITY.md](../SECURITY.md#verify-before-loading-ballast) |

## Banned words check

Before a release, search user-facing files for these and justify or remove each hit: `safe to delete`, `safe to
remove`, `speed up`, `speeds up`, `boost`, `optimis`, `optimiz`, `guarantee`, `100%`, `no risk`. Negations in
policy text ("never promises it is safe") and quotations of other projects' wording are fine.

Also search for the phrases `Markdown only` and `nothing to run`, and confirm each use is still true.
