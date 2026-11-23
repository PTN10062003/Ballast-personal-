# Codex storage and sidebar diagnosis

Use this optional report when the user asks what occupies their Codex storage or why a project or chat
still appears. Follow Ballast's integrity and consent steps. Establish which Codex host and profile the
user means. Windows Desktop, WSL and a remote host can each have different state. Ask whether they want
storage totals, [sidebar diagnosis](codex-sidebar.md), or both. A sidebar-only request needs no size scan.

## Storage totals

Use the owning host's effective settings. Resolve `CODEX_HOME` or its default `~/.codex`. Resolve
`sqlite_home` from the effective configuration first, then `CODEX_SQLITE_HOME`, then the Codex home.
Resolve relative settings against the owning process's working directory. Use its configured `log_dir`
when available. If the effective location is ambiguous, ask for it or mark the category unknown.
Keep config values inside the local probe. [Codex state locations](https://developers.openai.com/codex/config-advanced/#config-and-state-locations)
and [environment variables](https://learn.chatgpt.com/docs/config-file/environment-variables#core-locations).

Confirm the local roots in scope, especially redirected locations outside the profile. Count a backup
only when the user identifies its dedicated directory. Never search for backups or inventory a whole
workspace as a backup. Supply mount points from the OS as described in the
[path guard](../steps/06-approve-and-run.md#path-guard); withhold traversal if boundaries are unknown.
Run this Python 3.10+ probe locally under the scan's time limit. Pass the measured device number of
the report volume as `device`, repeating per volume when roots span devices. The default is the
Codex home's device. Catch I/O and validation failures locally and report “inventory unavailable”
without exception text or filenames. Return only the aggregate
result to the conversation. If a root can change concurrently, revalidate it and discard an unstable
measurement. An equivalent native probe must observe the same scope and privacy rules.

```python
import os
import re
import stat
import sys
from pathlib import Path


def storage_summary(home, sqlite_home=None, *, log_dir=None, backup_dir=None,
                    mount_points=None, device=None):
    def root_path(value):
        path = Path(value)
        if not path.is_absolute() or ".." in path.parts or path == Path(path.anchor):
            raise ValueError("Expected a specific absolute local directory")
        if os.name == "nt" and not re.fullmatch(r"[A-Za-z]:", path.drive):
            raise ValueError("Expected a local drive")
        return path

    home = root_path(home)
    db = root_path(sqlite_home) if sqlite_home is not None else home
    trees = {"sessions": home / "sessions", "archived_sessions": home / "archived_sessions",
             "diagnostics": root_path(log_dir) if log_dir is not None else home / "log"}
    if backup_dir is not None:
        trees["backups"] = root_path(backup_dir)
    for key, root in trees.items():
        if (any(p.is_relative_to(root) for p in (home, db))
                or any(p.is_relative_to(root) for k, p in trees.items() if k != key)):
            raise ValueError("Overlapping inventory roots")
    if mount_points is None and sys.platform.startswith("linux"):
        with open("/proc/self/mountinfo", "rb") as table:
            mount_points = [os.fsdecode(re.sub(rb"\\([0-7]{3})", lambda m: bytes([int(m[1], 8)]),
                                               line.split()[4])) for line in table]
    mounts = {Path(p) for p in (mount_points or ())}
    if device is None:
        device = home.lstat().st_dev

    def inspect(path):
        info = path.lstat()
        if (stat.S_ISLNK(info.st_mode)
                or getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT):
            raise ValueError("Redirected path")
        return info

    def measure(root, optional=False, db_files=False):
        keys = ("databases", "diagnostics") if db_files else ("tree",)
        rows = {k: {"files": 0, "bytes": 0, "coverage": "complete"} for k in keys}

        def mark(coverage):
            for row in rows.values():
                row["coverage"] = coverage

        try:
            for ancestor in reversed(root.parents):
                if not stat.S_ISDIR(inspect(ancestor).st_mode):
                    raise ValueError("Invalid ancestor")
            try:
                base = inspect(root)
            except FileNotFoundError:
                if optional:
                    return rows
                raise
            if not stat.S_ISDIR(base.st_mode):
                raise ValueError("Expected directory")
            if base.st_dev != device or (optional and root in mounts):
                mark("not selected")
                return rows
        except (OSError, ValueError):
            mark("unknown")
            return rows

        pending = [root]
        while pending:
            directory = pending.pop()
            try:
                if not stat.S_ISDIR(inspect(directory).st_mode):
                    raise ValueError("Directory changed")
                with os.scandir(directory) as children:
                    for child in children:
                        key = "tree"
                        if db_files:
                            family = re.fullmatch(r"(logs|state|goals|memories|history)_\d+\.sqlite(?:-(?:wal|shm|journal))?", child.name)
                            if not family:
                                continue
                            key = "diagnostics" if family[1] == "logs" else "databases"
                        path = Path(child.path)
                        try:
                            info = inspect(path)
                            if info.st_dev != base.st_dev or path in mounts or (
                                    os.name != "nt" and stat.S_ISDIR(info.st_mode) and path.is_mount()):
                                raise ValueError("Crosses mount boundary")
                            if stat.S_ISREG(info.st_mode):
                                rows[key]["files"] += 1
                                rows[key]["bytes"] += info.st_size
                            elif stat.S_ISDIR(info.st_mode) and not db_files:
                                pending.append(path)
                            else:
                                raise ValueError("Unexpected file type")
                        except (OSError, ValueError):
                            rows[key]["coverage"] = "partial"
            except (OSError, ValueError):
                mark("partial")
        return rows

    result = {}
    for key, path in trees.items():
        optional = key in ("sessions", "archived_sessions") or (key == "diagnostics" and log_dir is None)
        result[key] = measure(path, optional=optional)["tree"]
    result.setdefault("backups", {"bytes": 0, "files": 0, "coverage": "not selected"})
    database_rows = measure(db, db_files=True)
    result["databases"] = database_rows["databases"]
    file_logs, db_logs = result["diagnostics"], database_rows["diagnostics"]
    statuses = {file_logs["coverage"], db_logs["coverage"]} - {"not selected"}
    if len(statuses) == 1:
        file_logs["coverage"] = statuses.pop()
    else:
        file_logs["coverage"] = "partial" if statuses else "not selected"
    for field in ("files", "bytes"):
        file_logs[field] += db_logs[field]
    return result
```

Call `storage_summary` with the confirmed roots. Its five rows cover files in the active and archived
session directories, diagnostic logs, recognized versioned state databases, and the selected backup.
Database counts include WAL, SHM and rollback-journal companions. Coverage applies to these named
locations at observation time. Other files and unknown database layouts are outside this inventory.

## Present the result

Alongside either dashboard, show the host/volume and a short table with category, file count, logical
GiB and coverage. Use “at least” for partial measurements, “unknown” when inspection failed and
“outside this measurement” for unselected roots. Show backups on their own line. These informational
rows have no Clear choice and contribute zero to selected size and projected gain. Archiving keeps chat
history. Removing a database row does not establish that the filesystem released bytes. Use Ballast's
measured per-volume before/after delta following any separate approved operation.

If the user wants to hide a project, archive or restore a chat, or permanently delete history, explain
the effect and direct them to the owning Codex host's native workflow. For deletion, the affected
set may include spawned descendants. A Ballast selection never authorizes that operation. A verified
Codex maintenance skill can help on explicit request. A native refusal stays in effect.
