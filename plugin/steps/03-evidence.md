# Step 3: the eight checks

Never classify from a name, a location or a folder's own date. For every candidate, run these checks. They are
read-only. Record the result for each. **"Unknown" is a valid result, and it pushes the item to Grey.**

Before you descend into a candidate directory, apply the [whole-path guard](06-approve-and-run.md#path-guard)
and record its identity locally. A rejected path stays out of selection. The dashboard shows the eight checks
with plain names. The codes E1 to E8 are used in the scan data.

| Code | Plain name | The question | How (Windows example) |
|---|---|---|---|
| **E1** | **Last used** | When was anything inside last changed? (the newest *file*, not the folder's own date). Shown as information with a "Heads up" when recent; it never decides a tier by itself | `Get-ChildItem -LiteralPath $p -Recurse -Force -File -ErrorVariable e \| Sort-Object LastWriteTime -Descending \| Select -First 1`. **If `$e` is not empty, the answer is unknown** |
| **E2** | **In use now** | Is a process running from, or holding, this path? | Compare resolved paths by complete components, locally. Use the [local process probes](../catalog/orphan-processes-ram.md) and the [Temp lock check](../catalog/temp-and-recycle-bin.md#in-use-test) when applicable. Missing process information or a failed lock check withholds the item. |
| **E3** | **Is it a program?** | Is it an installed program or package rather than a cache? | Check package manifests and install registries (a package manager's `Packages` folder, Program Files). **Do not run anything you find** (H14), including `unins*.exe` |
| **E4** | **Anything depends on it** | Does anything point at it? | Virtual-environment `pyvenv.cfg` (`home =`), symbolic links and junctions, project config files that name it. Read these as text only |
| **E5** | **Unsaved work** | Is there source code or unsaved work inside? | Source trees and their untracked or modified files are protected. If a candidate is a Git worktree, withhold it. Avoid running Git commands that consult the discovered repository's configuration or helpers. |
| **E6** | **Cloud or shared** | Is it synced to the cloud or shared? | Path under OneDrive, Dropbox, Google Drive, a network share, or a mapped drive. A delete there spreads to every device |
| **E7** | **Protected name** | Does its name mark it as protected? | Match the patterns in [catalog/_protected.md](../catalog/_protected.md) |
| **E8** | **How to get it back** | What rebuilds it, and at what cost? | The command or action that regenerates it |

Recheck the same path identity before acting. See [step 6](06-approve-and-run.md#path-guard).

## Mistakes this step exists to prevent

These were real misjudgements made on a name or folder date, then corrected by evidence:

| Looked like | Was actually | Which check showed it |
|---|---|---|
| "Edge profile from 2022" (folder date) | A live profile used this week | Last used |
| "WinGet cache" (761 MB) | Installed programs (FFmpeg, Poppler, others) | Is it a program? |
| "Old Internet Explorer data" | Still written by another browser mode | Last used |
| "Spare Python install" | Held packages a project and a plugin needed | In use now, Anything depends on it |
| "Old chat history" in a tool folder | Same folder as the user's memory files | Protected name |

When a check is unknown or "in use", say so in the item's *why* line, quoting what you measured (H13).

## Attribution (who made it)

Also record how confident you are that an AI tool made the item: High, Medium or Low, using
[catalog/_attribution.md](../catalog/_attribution.md). Low means it might be the user's own work: Grey.
