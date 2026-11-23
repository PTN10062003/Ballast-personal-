# Codex sidebar diagnosis

Use this workflow when the user asks about Codex projects, chat ownership, or entries that remain visible after a project was removed. Report on the **owning host**. Windows, WSL, a remote host and a mobile client can show different workspaces. A missing local folder, a missing legacy key and absence from sidebar order are each insufficient evidence of deletion. Every category below is informational and stays out of Clear, group manifests and projected recovery.

## Collect a private, read-only snapshot

After the scan consent, explain that this optional diagnosis examines project IDs, chat IDs, assignment metadata and workspace roots locally. Only category counts and coverage reach the conversation. Record the owning host, installed version and current chat ID from the host context. Keep all identifiers and paths in memory on that host.

1. Use the active host's configured Codex home. In one local probe, parse only the known Desktop metadata file `.codex-global-state.json` as JSON, with closed file handles and without printing the file. Project its current project definitions (ID and every root), explicit thread assignments, project order and projectless IDs. If modern definitions and assignments are both absent, legacy saved roots can give a weaker path-only match. Require a stable snapshot; if the state changes during inventory, withhold the combined counts.
2. Use an existing trusted connection to that same host's App Server. Check its installed method schema supports `useStateDbOnly`. A plain `thread/list` may repair rollout metadata. On an initialized connection issue `thread/list` with the following parameters, starting with `cursor: null`. Follow each `nextCursor` to null, then repeat with `archived: true`. Include all source kinds supported by the installed schema and all providers. Omit cwd, search and section filters. The example lists the source kinds documented for this version. [App Server pagination and filters](https://learn.chatgpt.com/docs/app-server#list-threads-with-pagination--filters)

   ```json
   {"cursor":null,"limit":100,"archived":false,"modelProviders":[],"useStateDbOnly":true,"sourceKinds":["cli","vscode","exec","appServer","subAgent","subAgentReview","subAgentCompact","subAgentThreadSpawn","subAgentOther","unknown"]}
   ```

3. Project each page **inside the local probe** before any shell output, tool transcript, logging or report. From each record retain only its ID, cwd, archive state (from the query), and established project ID and chat kind. Never call a connector that returns raw titles, previews or chat text to the model for this inventory. Drop unrelated response fields immediately. Use host-provided relationships to identify generated workspaces, worktrees, automations and spawned chats. A missing source discriminator means unknown. Treat a repeated cursor, interrupted page, duplicate chat ID, unavailable local projection, unsupported read-only query or host mismatch as incomplete. Report “sidebar diagnosis unavailable” with a fixed reason. Do not substitute a sidebar page, compatibility index or broad disk search.

4. Use the following Python 3 classifier on the locally projected records. A thread has `id`, `cwd` (absolute path or null), `archived` (boolean), `kind`, and optionally `projectId`. Normalize reliable native relationship evidence to the kinds in the code. Use `interactive` only for known ordinary chats. Desktop assignments can omit cwd. The filesystem need not contain the saved cwd. On macOS, lexical matching uses case-sensitive components conservatively.

```python
import json
import os
import stat
from pathlib import Path, PurePosixPath, PureWindowsPath


def require(condition):
    if not condition:
        raise ValueError("Unsupported or incomplete sidebar metadata")


def identifier(value):
    return isinstance(value, str) and bool(value.strip())


def workspace_path(value, platform):
    if not identifier(value):
        return None
    if platform == "windows":
        value = value.replace("/", "\\")
        if value.lower().startswith("\\\\?\\unc\\"):
            value = "\\\\" + value[8:]
        elif value.startswith("\\\\?\\"):
            value = value[4:]
        if value.startswith("\\\\.\\"):
            return None
        path = PureWindowsPath(value)
    else:
        path = PurePosixPath(value)
    return path if path.is_absolute() and ".." not in path.parts else None


def sidebar_summary(state, threads, current_id, platform):
    require(isinstance(state, dict) and isinstance(threads, list) and identifier(current_id))
    require(platform in ("windows", "linux", "macos"))
    modern = "local-projects" in state or "thread-project-assignments" in state
    if modern:
        projects = state.get("local-projects")
        assignments = state.get("thread-project-assignments")
        require(isinstance(projects, list) and isinstance(assignments, dict))
    else:
        legacy = state.get("electron-saved-workspace-roots")
        require(isinstance(legacy, list))
        # Legacy roots identify paths only. Never fabricate current project membership.
        projects = [{"id": str(i), "rootPaths": [p]} for i, p in enumerate(legacy)]
        assignments = {}
    roots = {}
    for project in projects:
        require(isinstance(project, dict) and identifier(project.get("id")))
        pid = project["id"]
        require(pid not in roots and isinstance(project.get("rootPaths"), list))
        paths = [workspace_path(p, platform) for p in project["rootPaths"]]
        require(all(p is not None for p in paths))
        roots[pid] = paths
    projectless = state.get("projectless-thread-ids", [])
    require(isinstance(projectless, list) and all(identifier(i) for i in projectless))
    projectless = set(projectless)

    special = ("projectless", "automation", "worktree", "generated", "subagent")
    counts = dict.fromkeys(("current", "archived", *special, "assigned", "rootMatch", "unresolved"), 0)
    seen = set()
    for row in threads:
        require(isinstance(row, dict) and identifier(row.get("id")) and "cwd" in row)
        tid = row["id"]
        require(tid not in seen and type(row.get("archived")) is bool)
        require(row["cwd"] is None or isinstance(row["cwd"], str))
        kind = row.get("kind")
        require(kind in ("interactive", "unknown", *special))
        seen.add(tid)
        assignment = assignments.get(tid, {})
        require(isinstance(assignment, dict))
        desktop_id, native_id = assignment.get("projectId"), row.get("projectId")
        require(all(i is None or identifier(i) for i in (desktop_id, native_id)))
        known_ids = {i for i in (desktop_id, native_id) if i is not None}
        general = tid in projectless or kind == "projectless" or assignment.get("projectKind") == "projectless"
        cwd = workspace_path(row["cwd"], platform)
        matches = {pid for pid, paths in roots.items() if cwd is not None and
                   any(cwd == p or p in cwd.parents for p in paths)}
        status = "unresolved"
        if tid == current_id:
            status = "current"
        elif row["archived"]:
            status = "archived"
        elif assignment.get("pendingCoreUpdate") or len(known_ids) > 1 or (general and known_ids):
            pass
        elif general:
            status = "projectless"
        elif kind in special:
            status = kind
        elif known_ids:
            if modern and known_ids <= roots.keys() and (not matches or known_ids <= matches):
                status = "assigned"
        elif kind == "interactive" and len(matches) == 1 and tid not in assignments:
            status = "rootMatch"
        counts[status] += 1
    return counts


def summarize_native_pages(state, current_id, platform, list_page, source_kinds, kinds_by_id):
    """list_page runs locally and returns the unwrapped thread/list result."""
    require(isinstance(source_kinds, (list, tuple)) and source_kinds and all(map(identifier, source_kinds)))
    rows = []
    for archived in (False, True):
        cursor, visited = None, set()
        while True:
            page = list_page({"cursor": cursor, "limit": 100, "archived": archived,
                              "useStateDbOnly": True, "modelProviders": [], "sourceKinds": list(source_kinds)})
            require(isinstance(page, dict) and isinstance(page.get("data"), list) and "nextCursor" in page)
            for native in page["data"]:
                require(isinstance(native, dict) and identifier(native.get("id")))
                tid, source = native["id"], native.get("source")
                kind = kinds_by_id.get(tid)
                if kind is None:
                    if source in ("cli", "vscode"):
                        kind = "interactive"
                    elif isinstance(source, dict) and "subAgent" in source:
                        kind = "subagent"
                    else:
                        kind = "unknown"
                rows.append({"id": tid, "cwd": native.get("cwd"), "projectId": native.get("projectId"),
                             "archived": archived, "kind": kind})
            cursor = page["nextCursor"]
            if cursor is None:
                break
            require(identifier(cursor) and cursor not in visited)
            visited.add(cursor)
    return sidebar_summary(state, rows, current_id, platform)


def project_order_summary(state):
    projects, order = state.get("local-projects"), state.get("project-order")
    if not isinstance(projects, list) or not isinstance(order, list) or not all(map(identifier, order)):
        return None
    ids = [p.get("id") for p in projects if isinstance(p, dict)]
    if len(ids) != len(projects) or not all(map(identifier, ids)) or len(set(ids)) != len(ids):
        return None
    return {"definitions": len(ids), "outsideOrder": len(set(ids).difference(order))}


def desktop_sidebar_summary(home):
    """Local Desktop definitions and assignments only. No native history required."""
    root = Path(home)
    require(root.is_absolute() and ".." not in root.parts and root != Path(root.anchor))
    target = root / ".codex-global-state.json"
    for parent in reversed(target.parents):
        info = parent.lstat()
        require(stat.S_ISDIR(info.st_mode) and not getattr(info, "st_file_attributes", 0)
                & stat.FILE_ATTRIBUTE_REPARSE_POINT)
    before = target.lstat()
    require(stat.S_ISREG(before.st_mode) and not getattr(before, "st_file_attributes", 0)
            & stat.FILE_ATTRIBUTE_REPARSE_POINT)
    with target.open("rb") as stream:
        opened = os.fstat(stream.fileno())
        require(os.path.samestat(before, opened))
        state = json.load(stream)
        after = os.fstat(stream.fileno())
    final = target.lstat()
    require(os.path.samestat(opened, final) and opened.st_mtime_ns == after.st_mtime_ns == final.st_mtime_ns
            and opened.st_size == after.st_size == final.st_size)
    require(isinstance(state, dict) and isinstance(state.get("local-projects"), list)
            and isinstance(state.get("thread-project-assignments"), dict))
    projects = state["local-projects"]
    ids = {p["id"] for p in projects if isinstance(p, dict) and identifier(p.get("id"))}
    require(len(ids) == len(projects))
    counts = {"matchedAssignments": 0, "unresolvedAssignments": 0}
    projectless = state.get("projectless-thread-ids", [])
    require(isinstance(projectless, list) and all(map(identifier, projectless)))
    projectless = set(projectless)
    for tid, assignment in state["thread-project-assignments"].items():
        require(isinstance(assignment, dict))
        pid = assignment.get("projectId")
        if (identifier(pid) and pid in ids and not assignment.get("pendingCoreUpdate")
                and tid not in projectless and assignment.get("projectKind") != "projectless"):
            counts["matchedAssignments"] += 1
        else:
            counts["unresolvedAssignments"] += 1
    return {"projectOrder": project_order_summary(state), **counts}
```

Catch parse, I/O and validation failures locally and return a fixed availability message without exception text or partial records. Report exclusive counts for **database-listed chats** and any known coverage gaps. A project-order comparison is optional. Its second count means “defined projects absent from the saved order.” Pins and custom sections can also affect display. Where possible have the user check the actual sidebar after refresh. A discrepancy on a phone remains unverified until checked on that device.

For the native inventory, call `summarize_native_pages` with a **local** initialized client's
`thread/list` callback, the complete source-kind list for that host version and a local map of
confirmed special chat kinds by ID (an empty map is valid). Apply the probe timeout to the client
and the entire pagination loop. Print only the returned counts after verifying the snapshot is stable.

### Desktop-only coverage

If a private native thread listing is unavailable, run `desktop_sidebar_summary(home)` locally on
the confirmed owning host and print only its result. This measures saved assignment **records** and
project order. It cannot establish whether a given chat still exists, whether it is archived or how
many conversations appear on a device. A null project-order result means the order was unavailable.
Show this partial result with that coverage label. If the file is missing, redirected, unreadable,
changing or uses unsupported fields, show “Desktop assignment inventory unavailable”; keep parse
errors and raw state local. This route reads one file and never opens a rollout or SQLite database.

## When the user wants a change

Sidebar removal, chat archiving, permanent deletion and disk cleanup each need their own explicit intent. Direct the user to the owning host's built-in project Remove or chat Archive action when appropriate. For a refusal or a partially completed action, suggest read-only diagnosis with the separate Codex state specialist. Respect native writer and fork-dependency protections across clients. Ballast's file approval never authorizes a thread lifecycle operation, parent/child cascade, SQL write, database compaction, or transcript move. Archive normally retains history; only measured free-space changes establish a storage result.
