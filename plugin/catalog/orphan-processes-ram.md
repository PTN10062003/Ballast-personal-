# Processes AI tools leave running (memory)

Same tiers and rules as the rest of the catalog. **Stopping a process is a deletion-class action: ask first,
name the exact process ID, say what it is and what could be lost.**

## How to look

Start with the metadata-only inventory in [preflight](../steps/01-preflight.md). For a candidate PID,
evaluate the catalog match inside a single local tool call. These examples check for a `uvicorn` argument.
Use the relevant catalog term for other rows. Only the PID, parent PID, start time and match result may
leave this probe. Keep raw arguments out of tool output (including stderr), tracing, chat, logs and reports.

Windows PowerShell, with the integer `$candidatePid` from the inventory:

```powershell
try {
    $process = Get-CimInstance Win32_Process -Filter "ProcessId=$([uint32]$candidatePid)" -ErrorAction Stop
    if (-not $process -or -not $process.CommandLine -or -not $process.CreationDate) { throw 'Unavailable' }
    [pscustomobject]@{
        pid = $process.ProcessId
        parent = $process.ParentProcessId
        started = $process.CreationDate.ToUniversalTime().ToString('o')
        match = [bool]($process.CommandLine -match '(?:^|[\\/\s"''])uvicorn(?:\.exe)?(?:$|[\s"''])')
    } | ConvertTo-Json -Compress
} catch { '{"match":null}' }
```

On macOS or Linux use this local Python 3 probe with the candidate PID as its sole argument.
It captures the one `ps` result in memory and validates the metadata before printing it.

```python
import datetime
import json
import os
import re
import subprocess
import sys

result = {"match": None}
try:
    pid = int(sys.argv[1])
    if pid <= 0:
        raise ValueError
    output = subprocess.run(
        ["ps", "-ww", "-p", str(pid), "-o", "pid=,ppid=,lstart=,args="],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True,
        env={**os.environ, "LC_ALL": "C", "TZ": "UTC0"},
    ).stdout
    if len(output.splitlines()) != 1:
        raise ValueError
    pid_text, parent, day, month, date, clock, year, args = output.split(None, 7)
    if int(pid_text) != pid or not args.strip() or args.lstrip().startswith((b"[", b"(")):
        raise ValueError
    started = b" ".join((day, month, date, clock, year)).decode("ascii")
    stamp = datetime.datetime.strptime(started, "%a %b %d %H:%M:%S %Y")
    matched = re.search(rb"""(?:^|[/\s"'])uvicorn(?:$|[\s"'])""", args, re.I)
    result = {"pid": pid, "parent": int(parent), "started": stamp.isoformat() + "Z", "match": bool(matched)}
except (OSError, ValueError, subprocess.SubprocessError):
    pass
print(json.dumps(result))
```

A null match, uncertain argument visibility, incomplete metadata or a changed start time means unknown.
A match alone cannot establish ownership or an orphan. Check the parent, executable, working folder and
owner locally, ask if the user relies on the process, and apply the identity recheck below.

| ID | What | Tier | Evidence before stopping | Cost | Status |
|---|---|---|---|---|---|
| RAM-001 | Dev servers an agent started (for example `uvicorn`, `node`, `vite`, `next`, simple HTTP servers) | Yellow | Command line and working folder; whether the user started it or relies on it; parent session ended | In-memory state is lost; anything using that server stops | `review` |
| RAM-002 | Headless or automation browsers (headless Chrome, test browsers) | Yellow | No visible window; parent is gone or finished; not the user's own browser | Loses that automation run | `review` |
| RAM-003 | Cowork VM worker (`vmwp`) and `vmmem` | Yellow | The desktop app has been closed. The VM worker also serves other tools (WSL, Docker, sandboxes), so **prefer a reboot**. Stop one only if exactly one candidate matches the Claude VM, nothing else shares it, and the user approves | Stops the Cowork VM and its session, and a forced stop can corrupt the VM disk. Needs administrator rights, since it is a system process | `review` |
| RAM-004 | MCP servers started by agents (processes whose command line names an MCP server) | Yellow | The agent session that started them has ended | The server stops; it restarts with its agent | `review` |
| RAM-005 | Local model runners that keep a model loaded in memory (graphics memory too: see [gpu-memory.md](gpu-memory.md)) | Yellow | Prefer the tool's own stop command if it has one; no request is running | Next request reloads the model | `review` |

## Never stop, without naming it and asking

- Your own process ancestry (step 1) and anything in the same IDE or terminal.
- **Other agent sessions** (each is a separate process under the IDE or terminal).
- The user's browser, IDE, editor, and any server the user says they rely on.
- Security software and system processes.

## Rules

- Stop by **exact process ID**, never by name across the board. IDs get reused: immediately before stopping,
  re-match the ID, **start time, path and owner** (it must belong to the current user). If anything differs, stop
  and ask.
- Match command lines locally and report only yes or no. Do not print a whole command line (it can contain secrets).
- If a stop needs administrator rights, follow [permissions.md](../permissions.md): show **one** exact command and let
  the user run it. Never relaunch yourself elevated.
- Processes are never Green and are never part of a group approval.

## Verified

- RAM-003 (2026-11-02, Windows 11): the Cowork VM worker was not releasable by closing the app; it needed an
  administrator command. A live `uvicorn` server running from a project's virtual environment (RAM-001) was the
  user's own and was left running.
- RAM-001 to RAM-005 otherwise: not removed or confirmed across versions.
