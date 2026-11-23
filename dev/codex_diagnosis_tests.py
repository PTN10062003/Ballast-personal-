"""Exercise the packaged Codex diagnosis instructions on synthetic data only."""
import copy
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout


PLUGIN = Path(os.environ.get("BALLAST_TEST_PLUGIN", Path(__file__).resolve().parents[1] / "plugin"))


def load_probe(topic, function):
    document = (PLUGIN / "catalog" / f"codex-{topic}.md").read_text(encoding="utf-8")
    for block in re.findall(r"^```python\n(.*?)^```\s*$", document, re.S | re.M):
        if f"def {function}(" in block:
            namespace = {"__name__": "packaged_probe"}
            exec(compile(block, f"codex-{topic}.md", "exec"), namespace)
            return namespace[function]
    raise AssertionError(f"{function} missing from packaged instructions")


def project(name, *roots):
    return {"id": name, "rootPaths": list(roots)}


def thread(name, cwd=None, kind="interactive", archived=False, **extra):
    return {"id": name, "cwd": cwd, "kind": kind, "archived": archived, **extra}


class SidebarDiagnosis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.summary = staticmethod(load_probe("sidebar", "sidebar_summary"))

    def classify(self, state, rows, platform="windows"):
        original = copy.deepcopy((state, rows))
        output = io.StringIO()
        with redirect_stdout(output), redirect_stderr(output):
            result = self.summary(state, rows, "current-chat", platform)
        self.assertEqual(output.getvalue(), "")
        self.assertEqual((state, rows), original)
        self.assertEqual(set(result), {"current", "archived", "projectless", "automation", "worktree",
                                      "generated", "subagent", "assigned", "rootMatch", "unresolved"})
        self.assertTrue(all(type(n) is int and n >= 0 for n in result.values()))
        self.assertEqual(sum(result.values()), len(rows))
        return {bucket: count for bucket, count in result.items() if count}

    def test_25_valid_assignments_survive_absent_legacy_roots(self):
        rows = [thread(f"private-chat-{i}", r"D:\missing\old-checkout") for i in range(25)]
        state = {"local-projects": [project("hidden-project", r"D:\private\active")],
                 "project-order": [], "pinned-project-ids": [],
                 "thread-project-assignments": {r["id"]: {"projectId": "hidden-project"} for r in rows}}
        self.assertEqual(self.classify(state, rows), {"assigned": 25})

    def test_desktop_only_report_counts_saved_records_without_exposing_private_fields(self):
        snapshot = load_probe("sidebar", "desktop_sidebar_summary")
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp).resolve()
            file = home / ".codex-global-state.json"
            state = {"local-projects": [project("private-project", "/gone")], "project-order": [],
                     "thread-project-assignments": {f"private-chat-{i}": {"projectId": "private-project"}
                                                    for i in range(25)},
                     "unrelated": "private chat preview"}
            state["thread-project-assignments"]["pending"] = {"projectId": "missing"}
            state["thread-project-assignments"]["conflict"] = {"projectId": "private-project"}
            state["projectless-thread-ids"] = ["conflict"]
            file.write_text(json.dumps(state), encoding="utf-8")
            original = file.read_bytes()
            self.assertEqual(snapshot(home), {"projectOrder": {"definitions": 1, "outsideOrder": 1},
                                             "matchedAssignments": 25, "unresolvedAssignments": 2})
            self.assertEqual(file.read_bytes(), original)
            self.assertEqual(list(home.iterdir()), [file])

    def test_multiple_roots_and_conflicting_ownership(self):
        state = {"local-projects": [project("p", r"D:\Work\One", r"D:\Work\Two"),
                                    project("q", r"D:\other")],
                 "thread-project-assignments": {"orphan": {"projectId": "removed"},
                                                "conflict": {"projectId": "p"}},
                 "electron-saved-workspace-roots": [r"D:\stale"]}
        rows = [thread("second", r"d:\WORK\TWO\pkg"), thread("near", r"D:\Work\Twosome"),
                thread("orphan", r"D:\Work\One"), thread("conflict", r"D:\other", projectId="q"),
                thread("legacy", r"D:\stale")]
        self.assertEqual(self.classify(state, rows), {"rootMatch": 1, "unresolved": 4})

    def test_distinct_preserved_kinds_and_projectless_ids(self):
        state = {"local-projects": [], "thread-project-assignments": {},
                 "projectless-thread-ids": ["general-chat"]}
        special = ("automation", "worktree", "generated", "subagent")
        rows = [thread("current-chat"), thread("general-chat"), thread("archived-chat", archived=True)]
        rows.extend(thread(f"private-{kind}", kind=kind) for kind in special)
        self.assertEqual(self.classify(state, rows),
                         dict.fromkeys(("current", "projectless", "archived", *special), 1))

    def test_incomplete_or_ambiguous_inputs_withhold_the_diagnosis(self):
        modern = {"local-projects": [], "thread-project-assignments": {}}
        private_id = "private-unprinted-thread"
        for state, rows, current in [
            ({"local-projects": []}, [thread(private_id)], "current-chat"),
            (modern, [thread(private_id), thread(private_id)], "current-chat"),
            (modern, [{"id": private_id}], "current-chat"),
            (modern, [thread(private_id)], None),
        ]:
            with self.subTest(shape=len(rows), current_known=bool(current)), self.assertRaises(ValueError) as err:
                self.summary(state, rows, current, "linux")
            self.assertNotIn(private_id, str(err.exception))

    def test_local_pagination_fetches_both_scopes_and_drops_private_fields(self):
        probe = load_probe("sidebar", "summarize_native_pages")
        sources = ["cli", "vscode", "subAgent", "unknown"]
        state = {"local-projects": [], "thread-project-assignments": {}}
        calls = []

        def page(params):
            self.assertTrue(params["useStateDbOnly"])
            self.assertEqual(params["sourceKinds"], sources)
            self.assertEqual(params["modelProviders"], [])
            key = params["archived"], params["cursor"]
            calls.append(key)
            cursor = "next-page" if key == (False, None) else None
            return {"data": [{"id": "private-" + str(key), "preview": "personal text", "source": "cli"}],
                    "nextCursor": cursor}

        result = probe(state, "current-chat", "linux", page, sources, {})
        self.assertEqual(calls, [(False, None), (False, "next-page"), (True, None)])
        self.assertEqual({k: n for k, n in result.items() if n}, {"unresolved": 2, "archived": 1})
        with self.assertRaises(ValueError):
            probe(state, "current-chat", "linux", lambda _: {"data": [], "nextCursor": "same"}, sources, {})


class StorageDiagnosis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.summary = staticmethod(load_probe("storage", "storage_summary"))

    def setUp(self):
        workspace = tempfile.TemporaryDirectory()
        self.addCleanup(workspace.cleanup)
        self.base = Path(workspace.name).resolve()
        self.home = self.base / "codex"
        self.home.mkdir()

    def sample(self, relative, size):
        path = self.base / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x" * size)
        return path

    def test_relocated_databases_sidecars_and_backup_costs(self):
        sizes = {"codex/sessions/2026/private-title.jsonl": 17, "codex/archived_sessions/old.jsonl": 11,
                 "explicit-log/private-name.log": 5, "runtime/logs_2.sqlite": 19,
                 "runtime/logs_2.sqlite-shm": 7, "runtime/state_3.sqlite": 23,
                 "runtime/state_3.sqlite-wal": 13, "private-backup/threads-copy": 29,
                 "codex/state_3.sqlite": 37, "codex/log/old.log": 41, "codex/auth.json": 43,
                 "runtime/other-data.db": 47}
        paths = [self.sample(name, size) for name, size in sizes.items()]
        before = {p: (p.stat().st_mtime_ns, p.read_bytes()) for p in paths}
        output = io.StringIO()
        with redirect_stdout(output), redirect_stderr(output):
            result = self.summary(self.home, self.base / "runtime", log_dir=self.base / "explicit-log",
                                  backup_dir=self.base / "private-backup")
        self.assertEqual(output.getvalue(), "")
        expected = {"sessions": (1, 17), "archived_sessions": (1, 11), "diagnostics": (3, 31),
                    "databases": (2, 36), "backups": (1, 29)}
        self.assertEqual(result, {key: {"files": n, "bytes": size, "coverage": "complete"}
                                  for key, (n, size) in expected.items()})
        self.assertEqual({p: (p.stat().st_mtime_ns, p.read_bytes()) for p in paths}, before)
        self.assertEqual(set(p for p in self.base.rglob("*") if p.is_file()), set(paths))

    def test_missing_explicit_database_root_and_unrequested_backups(self):
        self.sample("codex/backups/retained", 9)
        result = self.summary(self.home, self.base / "missing-explicit")
        self.assertEqual(result["sessions"], {"bytes": 0, "files": 0, "coverage": "complete"})
        self.assertEqual(result["databases"]["coverage"], "unknown")
        self.assertEqual(result["backups"], {"bytes": 0, "files": 0, "coverage": "not selected"})

    def test_redirected_session_directory_withholds_external_bytes(self):
        self.sample("codex/sessions/closed.jsonl", 3)
        external = self.sample("elsewhere/private.jsonl", 53)
        link = self.home / "sessions" / "redirected"
        if os.name == "nt":
            subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
                            "$ErrorActionPreference = 'Stop'; New-Item -ItemType Junction "
                            "-Path $env:BALLAST_TEST_LINK -Target $env:BALLAST_TEST_TARGET | Out-Null"],
                           env={**os.environ, "BALLAST_TEST_LINK": str(link),
                                "BALLAST_TEST_TARGET": str(external.parent)}, check=True, timeout=30)
        else:
            link.symlink_to(external.parent, target_is_directory=True)
        result = self.summary(self.home)
        self.assertEqual(result["sessions"], {"bytes": 3, "files": 1, "coverage": "partial"})
        self.assertNotIn("private", json.dumps(result))
        self.assertEqual(external.read_bytes(), b"x" * 53)

    def test_mount_boundary_and_duplicate_categories(self):
        regular = self.sample("codex/sessions/ordinary", 2)
        mounted = self.sample("codex/sessions/mounted/untallied", 37).parent
        report = self.summary(self.home, mount_points=[mounted])
        self.assertEqual(report["sessions"], {"coverage": "partial", "files": 1, "bytes": 2})
        with self.assertRaises(ValueError):
            self.summary(self.home, backup_dir=regular.parent)
        off_volume = self.summary(self.home, device=regular.stat().st_dev + 1)
        self.assertEqual(off_volume["sessions"]["coverage"], "not selected")


if __name__ == "__main__":
    unittest.main()
