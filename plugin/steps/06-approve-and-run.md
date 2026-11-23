# Step 6: approve and run

Only now may anything be deleted, and only what the user approved (H0, H9).

## 1. Bind the choices to the scan

**Before presentation**, generate a fresh scan ID, record the platform and actual volume root, and keep your
own scan results in session state. Each item has a unique ID, exact full paths, logical sizes, identities,
tier, catalog row and removal method. A new scan invalidates earlier choices, even on the same day.

For a group, assign a group ID unique within this scan. Create its complete manifest once in a private
new report directory. Use ASCII identifiers of 1–64 characters from letters, digits, underscore and hyphen,
starting with a letter, digit or underscore. The adjacent filename is `<scanId>-<groupId>.json`.
The JSON object contains `scanId`, `groupId`, `volume`, `method` and `paths`. Each entry in `paths`
contains its exact absolute `path`, integer logical `sizeBytes` and the path guard's `identity`.
Group only disjoint eligible items on one volume with the same method, tier, rule and cost.
Use a real serializer, write UTF-8, and SHA-256 the **exact saved bytes**. Retain the binding separately
in current session state (scan ID, group ID, volume, method, count, lowercase hex SHA-256).
Do not replace or regenerate the file after presentation.

Show the full list or a link to it, the count, total logical size, row, method, digest and up to 50
largest entries clearly labeled as a sample. For a numbered Markdown reply, resolve its item number
only in the current report and show the entire binding again before asking for final approval. A pasted
dashboard request must match the current scan, volume, item IDs, exact paths or full group bindings.
Reject a mismatched or ambiguous request. Never take a manifest filename or a new path from the reply.

Before final approval **and again before execution**, read the saved manifest once, compare its byte
digest, scope and count to the retained binding and the user's selection/approval, and use only the
entries parsed from those verified bytes. If anything differs, withhold that group and request a new
review. In a verified clone, `python -B dev/approval.py create REPORT_DIR INPUT.json` creates a sidecar
from measured entries. `python -B dev/approval.py verify REPORT_DIR SCAN_ID RETAINED.json SELECTED.json`
checks the two six-field bindings. A text-only install performs the same serialization, hashing and
comparisons locally. Keep the report and sidecars together for the duration of review.

## 2. Get approval per item

Use the request format in [permissions.md](../permissions.md). The user's click on the dashboard **selects**; the
approval here **authorises**. A general "yes to everything" is not enough for Yellow items: confirm them
individually. State the scan ID, volume, method and full paths, or the group's complete binding and local
manifest link. Ask about that one group as a unit. For a large item, establish whether the Recycle Bin
can hold it before review (see section 5). A method change needs a new selection and approval.

## 3. Order

Green first, then Yellow. Within a group, smallest cost first. Stop on the first surprising result and re-assess.

## 4. Check right before each delete

Immediately before acting on **each entry**, compare its scan-time identity, repeat the lock check,
row-specific checks and [classification](04-classify.md). Skip and record a changed, missing, newly busy,
ineligible or unreadable entry. Continue with individually verified unchanged group members only.
Never substitute another path, recreate the group from a glob, or transfer an approval to a rescan.

### Path guard

Run the same guard **before measuring or offering** a candidate and immediately before acting on its
approved full path. Start at the verified current user's profile/home on a local fixed volume. Record the
OS volume ID and root identity for this scan. Standard user folders, the Temp root itself and all
[protected paths](../catalog/_protected.md) remain excluded. An exact catalog row may allow a specific
descendant of AppData. Never expand a wildcard into a deletion.

This read-only Python 3.10+ example checks the root, every intervening component, the candidate and its
descendants. On Linux supply mount points from the current mount namespace (including same-device bind
mounts); on macOS use the OS mount table. The trusted root may itself be a mount. Withhold the item if
volume or mount data, stable identities or complete directory listings are unavailable. An equivalent native
implementation must make the same checks.

```python
import hashlib
import json
import os
import re
import stat
from pathlib import Path


def path_identity(root_path, candidate, mount_points):
    root, target = Path(root_path), Path(candidate)
    if not root.is_absolute() or not target.is_absolute() or root not in target.parents:
        raise ValueError("outside the trusted root")
    if os.fspath(candidate) != str(target) or ".." in target.parts:
        raise ValueError("noncanonical path")
    if os.name == "nt":
        if not re.fullmatch(r"[A-Za-z]:", root.drive):
            raise ValueError("local drive required")
        for segment in target.parts[1:]:
            if re.search(r"~\d|[. ]$|[:*?]", segment):
                raise ValueError("ambiguous Windows path")

    mounts = {Path(p) for p in mount_points}
    root_info = root.lstat()
    records = []

    def inspect(path, inside):
        info = path.lstat()
        if (not info.st_ino or stat.S_ISLNK(info.st_mode)
                or getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
                or not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode))):
            raise ValueError("link, special file or unavailable identity")
        if inside and (info.st_dev != root_info.st_dev or path in mounts):
            raise ValueError("crossed mount or volume")
        if path.resolve(strict=True) != path:
            raise ValueError("redirected path")
        signature = [str(path), info.st_dev, info.st_ino, info.st_mode]
        if path == target or target in path.parents:
            signature.extend([info.st_size, info.st_mtime_ns, info.st_ctime_ns])
        records.append(signature)
        return stat.S_ISDIR(info.st_mode)

    for parent in reversed(target.parents):
        inspect(parent, root in parent.parents)
    pending = [target]
    while pending:
        path = pending.pop()
        if inspect(path, True):
            pending.extend(sorted(path.iterdir(), key=os.fspath))
    encoded = json.dumps(records, ensure_ascii=True, separators=(",", ":")).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()
```

On Linux build `mount_points` from field 5 of each line of `/proc/self/mountinfo`, unescaping octal
escapes (including spaces, tabs, newlines and backslashes). On macOS obtain the mounted-on paths through
`getmntinfo`. On Windows use an empty list after verifying the OS volume ID and fixed-drive type.
Pass the original absolute path string to the guard. Save its return value as the manifest entry's
`identity`. Do not normalize untrusted input first. Compare identities exactly, including the volume and
root identity, on the pre-action pass. A changed parent, newly added child, moved target or check error
means skip the affected entry. Never substitute the resolved destination or offer to delete the link.

Keep the recheck adjacent to the operation. A snapshot cannot prevent concurrent replacement between two
path-based calls. If another process could change the tree during the operation and the host cannot bind
the operation to the checked objects (for example using no-follow directory handles), skip it.

## 5. Methods (Windows examples)

**Recycle Bin (default for Yellow, and for Green when the user prefers).** It does not work for everything. An item
bigger than the Bin's limit, or on a drive without a Bin, can be deleted **permanently with no warning**. So:

1. Before review, if the item is larger than 4 GiB, or the Bin's capacity or the drive type is unclear,
   explain the risk. If the user wants a permanent removal, create and present a new binding for that
   method. An approval for a bin move cannot authorize permanent deletion.
2. Run:

   ```powershell
   Add-Type -AssemblyName Microsoft.VisualBasic
   [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteDirectory($path, 'OnlyErrorDialogs', 'SendToRecycleBin')   # folder
   [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile($path, 'OnlyErrorDialogs', 'SendToRecycleBin')       # file
   ```

3. After: verify the entry by original full path and volume in the volume-scoped bin inventory. If the
   outcome cannot be established, record it as unconfirmed. Re-measure free space on that volume.

Free space does not return until the Recycle Bin is emptied. Offer that **after** step 7 has verified that the
user's tools still work, and explain that emptying removes every entry in the current user's Bin on the
named volume, including entries from earlier sessions. Emptying
has its own two-step approval (the user looks in the Bin first, then confirms): see BIN-001 in
[catalog/temp-and-recycle-bin.md](../catalog/temp-and-recycle-bin.md).

**Permanent (Green caches the user approved, or an item the user chose to remove for good):**

```powershell
Remove-Item -LiteralPath $path -Recurse -Force -ErrorAction Stop
```

Use `-LiteralPath`. Never use shell tricks to bypass a refusal (H7). If a long path or lock stops it, report and
follow [permissions.md](../permissions.md).

**macOS and Linux:** use the system Trash (`osascript` or `trash` on macOS, `gio trash` on Linux). For a permanent
delete, never run `rm -r` with a variable you have not checked: the variable must be non-empty, absolute, resolved,
and on the manifest. Print the exact command to the user first.

## 6. Log as you go

Keep a running log: time, item, tier, size, method **as it actually happened**, result (deleted, moved, skipped,
blocked, failed) and the user's approval. Keep it in the conversation and, if the user agrees, in a report file
(step 7).

## 7. Handle blockers

Locked, needs admin, denied, partial: follow [permissions.md](../permissions.md). Never end a blocked item with only
"I can't". Ask for the permission you need and show the workaround.
