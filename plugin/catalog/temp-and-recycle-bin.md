# Temporary files and the Recycle Bin

AI tools, and everything they run (package installers, browsers, build tools), drop files in the user's Temp folder
and, when Ballast deletes something, the Recycle Bin holds it. Both can hold gigabytes. Same tiers and rules as the
rest of the catalog: read-only scan, evidence first, ask before every deletion.

**Temp is not just AI leftovers.** Any program may keep files there, and some of them are in use or hold work that
is not saved yet. So nothing in Temp is Green. It is Yellow when the evidence is complete, and Grey otherwise.

## The Temp folder

### Which folder

Use the long path `%LOCALAPPDATA%\Temp` inside the trusted profile. Compare its OS volume and file ID
with those of `%TEMP%` using opened directory handles or `os.path.samefile` in local Python. A mismatch
or unreadable identity means ask which folder the user means. Run the
[path guard](../steps/06-approve-and-run.md#path-guard) before descending. The Temp root is always
protected. Use only literal, individually checked child paths.

### How to look (read-only)

Measure with the commands in [steps/02-measure.md](../steps/02-measure.md): total size, file count, how the files
split by age, links, and the largest children. **Show every top-level item**, not only the largest: the user decides.
A first look can take about a minute for a thousand entries and ten thousand files. Say so, and run it with a time
limit.

### Rows

| ID | What | Tier | Evidence before deleting | Cost / rebuild | Status |
|---|---|---|---|---|---|
| TMP-001 | A folder or file directly inside `%LOCALAPPDATA%\Temp` that no other row names | Yellow when all of this holds, else Grey | **Last used:** shown, never a gate (a "Heads up" if it changed in the last day, since it may hold unsaved work; the user decides). **In use:** passes the [in-use test](#in-use-test), and no running process is started from inside it. **No links or junctions** inside. **Not a document's recovery file:** names starting `~$` or `~WRL` are Grey | Whatever program left it loses that leftover. A half-finished installer cannot resume. Permanent: the Recycle Bin is not used (see the method below) | `review` |
| TMP-002 | `pip-unpack-*` and other `pip-*` folders (pip's own unpacking folders) | Yellow when no pip is running and nothing inside is open | A local yes/no match that no running process has `pip` in its command line (never print the command line); passes the [in-use test](#in-use-test); no links | pip re-downloads and re-unpacks if it needs them again | `review` |
| TMP-003 | `claude\<project>\<session-id>\` (Claude Code session scratch) | As [CC-006](claude-code.md): Yellow when the session is finished, Grey if live | As CC-006. Never the folder of the session you are in | As CC-006 | `review` |
| TMP-004 | Anything in Temp that is in use, locked, unreadable, contains a link, or has a document-recovery name | **Grey** | Not selectable. Report the total and what is holding each one; it can be re-checked after the program closes. Recent changes alone do **not** make an item Grey | Not applicable | `review` |
| TMP-005 | `C:\Windows\Temp` (system Temp) | Grey | It is outside the user's profile, so the path guard refuses it, and clearing it needs administrator rights. Do not elevate. Show the user how to clear it themselves (Windows Settings, System, Storage, Temporary files) | Not applicable | `planned` |
| TMP-006 | `remotion-webpack-bundle-*`, `remotion-v*-assets*` and `puppeteer_dev_chrome_profile-*` (video-rendering and headless-browser tools that AI coding agents often drive) | Yellow when nothing is open and no render or browser process is running; **a render in progress makes them Grey** | Process list (yes/no match for `node`, `remotion` or a headless browser started from inside the folder); passes the [in-use test](#in-use-test); no links. Bundles can be about 1.9 GB each and are created again for every render | The next render rebuilds the bundle, which takes time | `review` (seen: two to three 1.9 GB bundles appeared during one render; nothing was deleted) |

### Many small files

Use the scan-time manifest and approval format in [step 6](../steps/06-approve-and-run.md). Show up to
30 of the largest qualifying top-level children of at least 50 MiB as individual items. Group the
remaining eligible entries without overlap. Include the full local manifest link, scan and group IDs,
volume, count, digest, logical size, Permanent method, catalog rule and a clearly labelled sample
of up to 50 paths. Keep the full list fixed through final approval. Recheck each approved entry and
record its result or individual skip reason.

### In-use test

For **every Temp row**, inspect the item and every file in it. An item passes only if enumeration succeeds
and each file opens exclusively. Check at scan time and immediately before the operation, after the path
guard both times. A lock, unreadable entry or enumeration failure withholds the whole candidate at selection
or records an individual skip after approval. An empty directory still needs all other applicable checks.

```powershell
function Test-TempUnlocked([string]$path) {
    try {
        $item = Get-Item -LiteralPath $path -Force -ErrorAction Stop
        $files = if ($item.PSIsContainer) {
            Get-ChildItem -LiteralPath $path -Recurse -Force -File -ErrorAction Stop
        } else { $item }
        foreach ($file in $files) {
            $handle = [IO.File]::Open($file.FullName, 'Open', 'Read', 'None')
            $handle.Dispose()
        }
        return $true
    } catch { return $false }
}
```

### Method

**Permanent**, with the user's approval, because moving temporary files to the Recycle Bin only fills it. Say plainly in
the approval request that Temp deletions cannot be undone. Use the delete in [steps/06](../steps/06-approve-and-run.md)
section 5, one path at a time.

## The Recycle Bin

| ID | What | Tier | Evidence before emptying | Cost | Status |
|---|---|---|---|---|---|
| BIN-001 | Current user's Recycle Bin on the scanned local fixed volume | Grey until inspected, then Yellow for a separate confirmation | Match the scan's volume ID, list and measure this volume's entries, and ask the user to inspect them | Every entry on that volume is permanently removed, including items from other programs and earlier sessions | `review` (emptying only mock-tested) |

### Inventory on Windows

Read the shell's combined view locally. Filter by the **actual bin entry's drive** before returning any
metadata. Keep the volume ID and full inventory in local scan state. The helper rejects unscoped entries,
incomplete metadata and volume changes. Use the profile volume from the scan as `$drive` (one letter) and
its recorded OS volume ID as `$volumeId`.

```powershell
function Read-BallastBin([string]$drive, [string]$volumeId) {
    if ($drive -notmatch '^[A-Za-z]$' -or -not $volumeId) { throw 'Missing scan volume' }
    $drive = $drive.ToUpperInvariant()
    $volume = Get-Volume -DriveLetter $drive -ErrorAction Stop
    if ($volume.DriveType -ne 'Fixed' -or $volume.UniqueId -ne $volumeId) { throw 'Volume changed' }
    $bin = (New-Object -ComObject Shell.Application -ErrorAction Stop).NameSpace(0xA)
    if (-not $bin) { throw 'Bin unavailable' }
    $collection = $bin.Items()
    if ($null -eq $collection) { throw 'Inventory unavailable' }
    $rows = @(foreach ($entry in $collection) {
        $id = [string]$entry.Path
        if ($id -notmatch '^[A-Za-z]:\\') { throw 'Unknown bin volume' }
        if ($id.Substring(0,1) -ne $drive) { continue }
        $size = $entry.ExtendedProperty('System.Size')
        $date = $entry.ExtendedProperty('System.Recycle.DateDeleted')
        $from = $entry.ExtendedProperty('System.Recycle.DeletedFrom')
        if ($null -eq $size -or [string]$size -eq '' -or [long]$size -lt 0 -or
            -not $date -or -not $from -or -not $entry.Name) { throw 'Incomplete bin entry' }
        [pscustomobject]@{ id = $id; name = $entry.Name; from = $from
            bytes = [long]$size; deleted = ([datetime]$date).ToUniversalTime().ToString('o') }
    })
    [long]$bytes = 0
    foreach ($row in $rows) { $bytes += $row.bytes }
    [pscustomobject]@{ drive = $drive; volumeId = $volume.UniqueId; count = $rows.Count
        bytes = $bytes; rows = @($rows | Sort-Object id) }
}

function Get-BinQuestion($inventory) {
    "Permanently empty the Recycle Bin on {0}: ({1} entries, {2} logical bytes), including older items?" -f
        $inventory.drive, $inventory.count, $inventory.bytes
}
```

Show only this volume's count, total logical bytes, oldest and newest deletion dates and 20 largest
items with their original folders. Identify which entries Ballast moved from the session log. An unreadable
or ambiguous inventory stays Grey. Keep the Bin separate from generic file selections.

### Emptying it

1. Save `$reviewed = Read-BallastBin $drive $volumeId` and show that volume's summary. Ask the user
   to inspect its entries themselves and wait for confirmation they have done so.
2. Show `Get-BinQuestion $reviewed` and wait for a separate explicit approval of the named volume, contents
   and Permanent method. Keep the reviewed inventory tied to this scan. A changed list needs fresh review.
3. Immediately before acting, run this block with the inventory saved at step 1. A missing or failed
   recheck stops the operation. Emptying a busy bin whose contents keep changing should be left to the user.

```powershell
$current = Read-BallastBin $reviewed.drive $reviewed.volumeId
if (($current | ConvertTo-Json -Depth 4 -Compress) -cne
    ($reviewed | ConvertTo-Json -Depth 4 -Compress)) { throw 'Bin changed. Review again.' }
Clear-RecycleBin -DriveLetter $reviewed.drive -Force -ErrorAction Stop
```

4. Re-read the same volume's bin, re-measure its free space, and report the observed result.
   Never delete inside the hidden `$Recycle.Bin` directory by path.

## macOS and Linux (starter rows, never observed)

| ID | Path | What it is | Tier | Notes | Status |
|---|---|---|---|---|---|
| TMP-M1 | `$TMPDIR` (macOS, per-user temp under `/var/folders/...`) | User temp | Grey | Same checks as TMP-001; find the path with `echo $TMPDIR`; do not guess | `planned` |
| TMP-L1 | `$TMPDIR` or `/tmp` entries **owned by the current user** (Linux) | User temp | Grey | `/tmp` is shared: never touch entries owned by anyone else | `planned` |
| BIN-M1 | `~/.Trash` (macOS) | Trash | Grey | Report only the measured volume. Keep emptying manual when the host's Trash operation combines volumes | `planned` |
| BIN-L1 | `~/.local/share/Trash` (Linux) | Trash | Grey | Report only the measured volume. A combined Trash operation cannot implement approval for one volume | `planned` |

## Verified

- 2026-11-02, Windows 11, Windows PowerShell 5.1, one laptop. **Temp, read-only:** 1.45 GB in 9,405 files; 48 files
  (0.01 GB) older than 7 days; no links; no read errors; about 20 seconds. The largest children were `claude`
  (0.23 GB) and seven `pip-unpack-*` folders (0.06 to 0.15 GB each). `%TEMP%` was an 8.3 short name; the long form
  `%LOCALAPPDATA%\Temp` was confirmed as the same folder (same creation time and child names). The in-use test
  correctly reported a dummy file as free, then in use while it was held open, then free again.
- A fuller read-only scan on the same laptop later that day listed **every** top-level entry: 1,487 entries, 1.75 GB,
  about 54 seconds. 1,452 were `pip-*` folders (1.47 GB), 1 was the Claude Code scratch folder (0.23 GB), 28 were in
  use, unreadable or held a link (under 0.01 GB together), and the other 6 were small. With age shown but not used
  as a gate, 1,458 entries were Yellow and 29 were Grey.
- **First real deletion** (2026-11-02, author's laptop): see C14 in [dev/tests.md](https://github.com/chittychat-studio/Ballast/blob/main/dev/tests.md). 1,771 Temp entries, 2.09 GB, were
  deleted from an approved manifest; 100 were skipped and 1 failed because another process held it open. During the same
  hour a video render kept adding about 1.9 GB bundles, so free space fell although Ballast freed space.
- **Recycle Bin, read-only (the author's laptop; always measure your own):** the shell view read it and reported 0
  items (it had been emptied earlier). Nothing was
  deleted by these rows, and `Clear-RecycleBin` was **not** run, so BIN-001 emptying is untested.
