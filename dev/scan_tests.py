"""Acceptance fixtures that execute the probes shipped in the text-only plugin."""
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import tempfile
import unittest

from approval import create, file_tier, group_preview, verify
from dashboard_report import generate

CATALOG = Path(__file__).resolve().parents[1] / "plugin" / "catalog"
TEMP_DOC = CATALOG / "temp-and-recycle-bin.md"
RAM_DOC = CATALOG / "orphan-processes-ram.md"
GUARD_DOC = CATALOG.parent / "steps" / "06-approve-and-run.md"


def snippet(document, heading, language):
    section = document.read_text(encoding="utf-8").split(heading + "\n", 1)[1]
    return section.split("```" + language + "\n", 1)[1].split("\n```", 1)[0]


def powershell(script, *arguments):
    command = "$ErrorActionPreference = 'Stop'\n$args = ConvertFrom-Json $env:BALLAST_FIXTURE_ARGS\n" + script
    return subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
        env={**os.environ, "BALLAST_FIXTURE_ARGS": json.dumps(list(map(str, arguments)))},
        capture_output=True, text=True, timeout=45,
    )


class ScanFixtures(unittest.TestCase):
    def test_process_probe_outputs_metadata_only(self):
        marker = "private-fixture-" + secrets.token_hex(16)
        with subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)", "uvicorn", marker]) as child:
            try:
                if os.name == "nt":
                    code = "$candidatePid = [int]$args[0]\n" + snippet(RAM_DOC, "## How to look", "powershell")
                    observed = powershell(code, child.pid)
                else:
                    code = snippet(RAM_DOC, "## How to look", "python")
                    observed = subprocess.run([sys.executable, "-c", code, str(child.pid)],
                                              capture_output=True, text=True, timeout=10)
            finally:
                child.terminate()
        # Even a failing regression must not echo the marker to the test runner.
        self.assertFalse(marker in observed.stdout + observed.stderr, "Private argument reached a shell stream")
        self.assertEqual(observed.returncode, 0, observed.stderr)
        self.assertEqual(observed.stderr, "")
        value = json.loads(observed.stdout)
        self.assertEqual(set(value), {"pid", "parent", "started", "match"})
        self.assertEqual(value["pid"], child.pid)
        self.assertTrue(value["match"])
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            transcript = folder / "tool-transcript.json"
            transcript.write_text(json.dumps({"role": "tool", "invocation": observed.args,
                                              "stdout": observed.stdout, "stderr": observed.stderr}),
                                  encoding="utf-8")
            log = folder / "scan.jsonl"
            log.write_text(json.dumps({"check": "process match", "result": value}) + "\n", encoding="utf-8")
            report = folder / "report.html"
            platform = {"win32": "windows", "darwin": "macos"}.get(sys.platform, "linux")
            generate({"schema": 2, "platform": platform, "volume": folder.resolve().anchor, "scanId": "process-fixture",
                      "freeGiB": 1, "totalGiB": 2, "scopeNote": json.dumps(value), "items": []}, report)
            for artifact in (transcript, log, report):
                data = artifact.read_bytes()
                self.assertIn(str(child.pid).encode(), data)
                self.assertFalse(marker.encode() in data, f"Private argument reached {artifact.name}")

    def test_path_guard_at_selection_and_action(self):
        namespace = {}
        exec(snippet(GUARD_DOC, "### Path guard", "python"), namespace)
        identity = namespace["path_identity"]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            nested = root / "profile" / "cache"
            nested.mkdir(parents=True)
            candidate = nested / "data"
            candidate.touch()
            intact = identity(root, str(candidate), [])
            reached = []

            def mock_action(target, expected):
                try:
                    if identity(root, str(target), []) == expected:
                        reached.append(target)
                except (OSError, ValueError):
                    pass

            mock_action(candidate, intact)
            with self.assertRaises(ValueError):
                identity(root, str(candidate), [nested])
            with self.assertRaises(ValueError):
                identity(root, str(root.parent), [])
            candidate.rename(nested / "old")
            candidate.touch()
            mock_action(candidate, intact)
            target = root / "elsewhere"
            target.mkdir()
            (target / "data").touch()

            def directory_link(link, destination):
                if os.name == "nt":
                    result = powershell("New-Item -ItemType Junction -Path $args[0] -Target $args[1] | Out-Null",
                                        link, destination)
                    self.assertEqual(result.returncode, 0, result.stderr)
                else:
                    link.symlink_to(destination, target_is_directory=True)

            linked_parent = root / "redirect"
            directory_link(linked_parent, target)
            with self.assertRaises(ValueError):
                identity(root, str(linked_parent / "data"), [])
            folder_identity = identity(root, str(nested), [])
            mock_action(nested, folder_identity)
            directory_link(nested / "redirect", target)
            with self.assertRaises(ValueError):
                identity(root, str(nested), [])
            mock_action(nested, folder_identity)
            self.assertEqual(reached, [candidate, nested])

    def test_browser_profile_allowlist(self):
        catalog = (CATALOG / "windows-and-app-caches.md").read_text(encoding="utf-8")
        policy = json.loads((CATALOG.parent / "policy.json").read_bytes())
        for row_id in ["BR-001", "BR-002"]:
            row = next(line for line in catalog.splitlines() if line.startswith("| " + row_id + " |"))
            allowed = re.findall(r"`([^`]+)`", row.split("|")[2])
            self.assertCountEqual(allowed, ["Cache", "Code Cache", "GPUCache"])
            with tempfile.TemporaryDirectory() as tmp:
                profile = Path(tmp)
                storage = profile / "Service Worker" / "CacheStorage"
                storage.mkdir(parents=True)
                (storage / "stored-response").write_bytes(b"local offline content")
                os.utime(storage, (946684800, 946684800))
                for name in ["Cache", "Code Cache", "GPUCache"]:
                    (profile / name).mkdir()
                for browser_open in (True, False):
                    evidence = [{"id": key, "state": "ok", "text": "Confirmed in fixture"}
                                for key in policy["checks"]]
                    next(check for check in evidence if check["id"] == "E2").update(
                        state="block" if browser_open else "ok", text="Measured browser state")
                    record = {"tier": "Yellow", "maker": "High", "method": "Recycle Bin",
                              "catalogRow": row_id, "evidence": evidence}
                    offered = [profile / name for name in allowed if (profile / name).is_dir()
                               and file_tier(record, "windows", policy) == "Yellow"]
                    self.assertEqual(len(offered), 0 if browser_open else 3)
                    self.assertFalse(any(path in storage.parents or path == storage for path in offered))
        self.assertIn("CacheStorage", (CATALOG / "_protected.md").read_text(encoding="utf-8"))

    @unittest.skipUnless(os.name == "nt", "Windows file-sharing and ACL semantics")
    def test_locked_and_unreadable_temp(self):
        rows = TEMP_DOC.read_text(encoding="utf-8").splitlines()
        for row_id in ["TMP-001", "TMP-002", "TMP-006"]:
            row = next(line for line in rows if line.startswith("| " + row_id + " |"))
            self.assertIn("passes the [in-use test](#in-use-test)", row)
        code = snippet(TEMP_DOC, "### In-use test", "powershell") + """
$free = Join-Path $args[0] 'free'
$busy = Join-Path $args[0] 'busy'
$denied = Join-Path $args[0] 'denied'
foreach ($p in @($free,$busy,$denied)) { [IO.File]::WriteAllText($p, '') }
$original = [IO.File]::GetAccessControl($denied)
$restricted = [IO.File]::GetAccessControl($denied)
$account = [Security.Principal.WindowsIdentity]::GetCurrent().User
$rule = [Security.AccessControl.FileSystemAccessRule]::new($account,'ReadData','Deny')
$restricted.AddAccessRule($rule)
$handle = [IO.File]::Open($busy, 'Open', 'Read', 'None')
try {
    [IO.File]::SetAccessControl($denied, $restricted)
    $eligible = @(@($free,$busy,$denied) | Where-Object { Test-TempUnlocked $_ })
    $parentPass = Test-TempUnlocked $args[0]
    $laterLock = [IO.File]::Open($free, 'Open', 'Read', 'None')
    try {
        $results = @(foreach ($p in $eligible) {
            if (Test-TempUnlocked $p) { 'mock delete' } else { 'skipped' }
        })
    } finally { $laterLock.Dispose() }
    [pscustomobject]@{ eligible = @($eligible | Split-Path -Leaf)
        folder = $parentPass; results = $results } | ConvertTo-Json -Compress
} finally {
    $handle.Dispose()
    [IO.File]::SetAccessControl($denied, $original)
}
"""
        with tempfile.TemporaryDirectory() as tmp:
            run = powershell(code, tmp)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(json.loads(run.stdout), {"eligible": ["free"], "folder": False, "results": ["skipped"]})

    @unittest.skipUnless(os.name == "nt", "Windows exclusive-open semantics")
    def test_approved_group_skips_just_the_newly_busy_entry(self):
        namespace = {}
        exec(snippet(GUARD_DOC, "### Path guard", "python"), namespace)
        identity = namespace["path_identity"]
        # Keep one PowerShell open so each path gets a fresh exclusive-open check
        # at the point of selection or action, without starting 102 shells.
        code = snippet(TEMP_DOC, "### In-use test", "powershell") + """
while ($null -ne ($line = [Console]::ReadLine())) {
    $file = ConvertFrom-Json -InputObject $line
    if (Test-TempUnlocked $file) { [Console]::WriteLine('free') }
    else { [Console]::WriteLine('busy') }
}
"""
        with tempfile.TemporaryDirectory() as tmp, subprocess.Popen(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", code],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True) as probe:
            def is_free(path):
                probe.stdin.write(json.dumps(str(path)) + "\n")
                probe.stdin.flush()
                result = probe.stdout.readline().strip()
                self.assertIn(result, ("free", "busy"))
                return result == "free"

            try:
                directory = Path(tmp).resolve()
                root = directory / "profile"
                root.mkdir()
                files = [root / f"{n:02}.tmp" for n in range(51)]
                entries = []
                for n, file in enumerate(files):
                    file.write_bytes(b"x" * n)
                    signature = identity(root, str(file), [])
                    self.assertTrue(is_free(file))
                    entries.append({"path": str(file), "sizeBytes": file.stat().st_size, "identity": signature})

                scan = "busy-after-approval"
                retained = create(directory, {"scanId": scan, "groupId": "temp", "volume": root.anchor,
                                               "method": "Permanent", "paths": entries})
                # A copied selection and its separately confirmed binding take a JSON round trip.
                selected = json.loads(json.dumps(retained))
                reviewed = verify(directory, scan, retained, selected)
                preview = group_preview(reviewed)["paths"]
                self.assertEqual(retained["count"], 51)
                self.assertEqual(len(preview), 50)
                approved = dict(selected)
                busy = files[0]
                self.assertNotIn(str(busy), [row["path"] for row in preview])

                reached, skipped = [], []
                with busy.open("rb"):
                    for entry in verify(directory, scan, retained, approved):
                        path = entry["path"]
                        if identity(root, path, []) != entry["identity"]:
                            skipped.append((path, "identity changed"))
                        elif not is_free(path):
                            skipped.append((path, "busy or unreadable"))
                        else:
                            reached.append(path)  # mock operation
                self.assertEqual(reached, [str(file) for file in files[1:]])
                self.assertEqual(skipped, [(str(busy), "busy or unreadable")])
            finally:
                probe.stdin.close()

    @unittest.skipUnless(os.name == "nt", "PowerShell and Windows path semantics")
    def test_bin_inventory_confirmation_and_operation_scope(self):
        setup = r"""
function New-FixtureEntry($drive,$bytes) {
    $row = [pscustomobject]@{ Path = "${drive}:\fixture-bin\one"; Name = 'one'; Bytes = $bytes }
    $row | Add-Member ScriptMethod ExtendedProperty {
        param($property)
        switch ($property) {
            'System.Size' { $this.Bytes }
            'System.Recycle.DeletedFrom' { 'fixture folder' }
            'System.Recycle.DateDeleted' { [datetime]'2026-01-10T10:00:00Z' }
        }
    }
    $row
}
$script:entries = @((New-FixtureEntry C 101), (New-FixtureEntry D 202))
function Get-Volume($DriveLetter) { [pscustomobject]@{ UniqueId = "fixture-$DriveLetter"; DriveType = 'Fixed' } }
function New-Object {
    $shell = [pscustomobject]@{}
    $shell | Add-Member ScriptMethod NameSpace {
        $bin = [pscustomobject]@{}
        $bin | Add-Member ScriptMethod Items { $script:entries }
        $bin
    }
    $shell
}
$script:operations = @()
function Clear-RecycleBin($DriveLetter,[switch]$Force) { $script:operations += $DriveLetter }
"""
        inventory = snippet(TEMP_DOC, "### Inventory on Windows", "powershell")
        operation = snippet(TEMP_DOC, "### Emptying it", "powershell")
        script = setup + inventory + """
$reviewed = Read-BallastBin D fixture-D
$question = Get-BinQuestion $reviewed
""" + operation + """
$script:entries[1].Bytes = 303
try {
""" + operation + """
} catch { $changed = $true }
[pscustomobject]@{ count = $reviewed.count; bytes = $reviewed.bytes; question = $question
    operations = $script:operations; changed = $changed } | ConvertTo-Json -Compress
"""
        run = powershell(script)
        self.assertEqual(run.returncode, 0, run.stderr)
        output = json.loads(run.stdout)
        self.assertEqual((output["count"], output["bytes"]), (1, 202))
        self.assertIn("D:", output["question"])
        self.assertNotIn("C:", output["question"])
        self.assertEqual(output["operations"], ["D"])
        self.assertTrue(output["changed"])


if __name__ == "__main__":
    unittest.main()
