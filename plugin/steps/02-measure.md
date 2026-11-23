# Step 2: measure (read-only)

Goal: sizes for known AI leftovers, plus a short list of large unknown folders. Change nothing.

## 1. Known targets

Record the platform, actual mount or drive root, stable volume ID, free bytes and capacity.
Create a separate report per volume. Resolve the user's home/profile through the OS. A redirected
profile may be on a drive such as D:. Use the [whole-path guard](06-approve-and-run.md#path-guard)
before traversing a candidate. Withhold anything outside the verified scope.

For each applicable catalog row, measure logical file lengths and the newest file date. Windows example
for an already guarded path:

```powershell
$path = "$env:LOCALAPPDATA\<the row's path>"
if ([string]::IsNullOrWhiteSpace($path) -or -not (Test-Path -LiteralPath $path)) { return }
$files = Get-ChildItem -LiteralPath $path -Recurse -Force -File -ErrorAction SilentlyContinue -ErrorVariable measureErrors
($files | Measure-Object Length -Sum).Sum    # logical bytes, not reclaimed allocation
$files | Sort-Object LastWriteTime -Descending | Select-Object -First 1 LastWriteTime, Name
```

**Check `$measureErrors`.** If any subfolder could not be read, the size and the newest date are incomplete:
report them as "at least" and mark the dates **unknown** (H2). Do not treat hidden errors as "nothing there".

On macOS and Linux, sum `lstat().st_size` for regular files on the guarded tree without following links.
For recency use their newest modification time. Record unrounded bytes and convert to GiB
using 1,073,741,824 bytes per GiB at display time. A sum of logical lengths describes the selected
paths. It does not establish how much space the filesystem will release.

**Immediate gain and pending space.** For a same-volume Recycle Bin/Trash move, estimated immediate
gain is zero. Report the selected logical bytes pending in that volume's bin. For a permanent removal,
use allocated bytes only when you can identify the underlying allocations and establish that every
reference will be released. Deduplicate by stable volume and allocation ID across the entire selection.
Account for hard links outside the selection, sparse files, clones, snapshots, compression and
overlapping parent/child selections. Keep report items disjoint when constructing them. When the
filesystem cannot prove reclaimable allocation, omit the estimate and report **unknown**. Never
substitute logical bytes or a rounded GiB figure. Re-measure each volume after acting.

**Links and junctions.** Do not follow them. If a folder contains a symbolic link or junction (reparse point),
note it. Measuring through one can report the size and dates of somewhere else entirely:

```powershell
Get-ChildItem -LiteralPath $path -Recurse -Force -Attributes ReparsePoint -ErrorAction SilentlyContinue | Select-Object FullName, LinkType, Target
```

Rows with no matching path are simply absent: skip them quietly.

## 1a. The Temp folder and the Recycle Bin (read-only)

Always measure both on Windows. Verify the long Temp path and its ancestors and confirm it identifies
the same directory as `%TEMP%` ([Temp catalog](../catalog/temp-and-recycle-bin.md)). List immediate
children without following links. Run the path guard on each child before descending into it. Sum the
guarded measurements for this volume and record how many entries could not be measured. Show the count
and logical GiB modified in the past 24 hours as information about recency.

A large Temp folder can take a while (about 20 seconds for ten thousand files): say so and run it with a time limit.
Any read error means the totals are "at least" and the affected items are Grey (H2). Report the Recycle Bin's item
count, size and dates using the volume-scoped inventory in [BIN-001](../catalog/temp-and-recycle-bin.md).
The inventory, confirmation, action and final free-space reading must name the same volume.

## 1b. Graphics memory (read-only, optional)

If the user uses local models or image tools (or asks about slowness), read graphics memory as described in
[catalog/gpu-memory.md](../catalog/gpu-memory.md): the adapter, dedicated and shared usage, and which processes hold
it. Report numbers you measured and "not measured" for anything you could not read. This changes nothing. Stopping a
process that holds graphics memory goes through the same ask-first rules as any process.

## 2. Unknown space (AI-related roots first)

Measure the immediate children of the places where AI tools commonly leave things, largest first, top 15 each:

- the home folder's dot-folders (`%USERPROFILE%\.*`, `~/.*`)
- `%LOCALAPPDATA%` and `%APPDATA%` (Linux: `~/.local/share`, `~/.cache`, `~/.config`)
- the user's projects or code folders, one level down

Then list the largest individual files over 200 MB in the user's profile, **excluding** Red locations
([catalog/_protected.md](../catalog/_protected.md)). For Red locations you may report a total size so the user
understands where space goes, but never list their contents for deletion.

## 3. Report totals, not conclusions

Show a short table: item, size, newest file date, which catalog row it matched (or "unknown"). Do not classify
yet. Unknown large folders go to step 3 for evidence.

## 4. Mind the cost

If a scan is slow, say so, run it in the background with a time limit, and tell the user. Stop anything you
started when done (H12).
