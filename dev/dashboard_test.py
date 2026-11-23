"""Generate reports using the documented CLI and exercise the offline page in Chromium."""
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

from playwright.sync_api import sync_playwright

import approval
from dashboard_report import DATA_TAG, ROOT, TEMPLATE

GIB = 2**30
VOLUME = "D:\\"
FIXTURE_TEXT = 'Report </script> <em> “quotes” & Ω'


def item(number, suffix=None):
    return {
        "id": number, "name": f"Candidate {number}", "tool": "Fixture tool", "tier": "Green",
        "maker": "High", "catalogRow": "CD-002", "method": "Permanent", "volume": VOLUME,
        "sizeGiB": 1, "paths": [{"path": VOLUME + "Users\\Example\\" + (suffix or f"Cache{number}"),
                                  "sizeGiB": 1}],
        "why": FIXTURE_TEXT, "cost": "Regenerates on next use.",
        "evidence": [{"id": f"E{i}", "state": "ok", "text": f"Fixture check {i} passed."}
                     for i in range(1, 9)],
    }


def scan(items):
    return {"schema": 2, "example": False, "scanId": "scan-1", "platform": "windows",
            "volume": VOLUME, "scanDate": "2026-01-01", "freeGiB": 10, "totalGiB": 64,
            "items": items}


class Dashboard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.playwright = sync_playwright().start()
        cls.addClassCleanup(cls.playwright.stop)
        cls.browser = cls.playwright.chromium.launch(executable_path=os.getenv("BALLAST_CHROMIUM"))
        cls.addClassCleanup(cls.browser.close)

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)
        self.context = self.browser.new_context(offline=True)
        self.addCleanup(self.context.close)
        self.page = self.context.new_page()
        self.errors = []
        self.page.on("pageerror", lambda error: self.errors.append(str(error)))

    def tearDown(self):
        self.assertEqual(self.errors, [])

    def generate(self, data, success=True):
        source, report = self.folder / "scan.json", self.folder / "report.html"
        source.write_text(json.dumps(data), encoding="utf-8")
        proc = subprocess.run([sys.executable, "-B", str(ROOT / "dev/dashboard_report.py"),
                               str(source), str(report)], capture_output=True, text=True)
        if not success:
            self.assertNotEqual(proc.returncode, 0)
            self.assertFalse(report.exists())
            return
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.page.goto(report.as_uri())
        return report

    def choose(self, number):
        self.page.locator(f'#clearlist input[data-item="{number}"]').check()

    def test_full_document_and_policy(self):
        fixture = [item(i) for i in range(1, 6)]
        fixture[0]["evidence"].pop()
        fixture[1]["evidence"][1]["state"] = "block"
        fixture[2]["evidence"][6]["state"] = "block"
        fixture[2]["evidence"].pop(0)  # Red still wins over a missing check.
        fixture[4]["evidence"][2]["state"] = "na"
        report = self.generate(scan(fixture))
        source = report.read_text(encoding="utf-8")
        encoded = source.split(DATA_TAG)[1].split("</script>")[0]
        self.assertNotIn("<", encoded)
        self.assertIn(r"\u003c", encoded)
        self.assertEqual(json.loads(encoded)["items"][3]["why"], FIXTURE_TEXT)
        self.assertEqual(self.page.locator("script").count(), 2)
        self.assertEqual(self.page.locator("body em").count(), 0)
        self.assertEqual(self.page.locator("#clearlist input").count(), 1)
        self.assertIn("Held back 3", self.page.locator("#vtabs").inner_text())
        self.assertIn("Protected 1", self.page.locator("#vtabs").inner_text())
        markdown = subprocess.run([sys.executable, "-B", str(ROOT / "dev/approval.py"), "choices",
                                   str(self.folder / "scan.json")], capture_output=True, text=True, check=True)
        self.assertIn("| 4 | Yellow | Keep / Clear |", markdown.stdout)
        self.assertEqual(markdown.stdout.count("Keep / Clear"), 1)
        self.assertIn("| 3 | Red | Keep |", markdown.stdout)
        self.choose(4)
        self.page.get_by_role("button", name="Candidate 4", exact=True).first.click()
        self.assertIn(FIXTURE_TEXT, self.page.locator("#pane-d").inner_text())
        self.assertEqual(self.page.locator("#addr").inner_text(), fixture[3]["paths"][0]["path"])
        self.assertIn(fixture[3]["paths"][0]["path"], self.page.locator("#reply").input_value())
        self.assertIn("method Permanent", self.page.locator("#reply").input_value())
        self.assertIn("gain unknown", self.page.locator("#sum").inner_text())
        renderer = re.search(r"<script>(.*?)</script>", source, re.S)[1]
        pin = base64.b64encode(hashlib.sha256(renderer.encode()).digest()).decode()
        self.assertIn(f"script-src 'sha256-{pin}';", source)
        decision = re.search(r"^var POLICY=(.+);$", renderer, re.M)[1]
        self.assertEqual(json.loads(decision), json.loads((ROOT / "plugin/policy.json").read_bytes()))
        self.assertEqual(source.split(DATA_TAG)[0], TEMPLATE.read_text(encoding="utf-8").split(DATA_TAG)[0])

    def test_measured_results_and_empty_scan(self):
        data = scan([])
        data["runs"] = [{"label": "Fixture", "volume": VOLUME, "freeBeforeGiB": 11, "freeAfterGiB": 10,
                         "cleared": 1, "clearedGiB": 1, "skipped": 0, "failed": 0}]
        self.generate(data)
        self.assertTrue(self.page.locator("#emptystate").is_visible())
        self.assertIn("-1.0 GiB", self.page.locator("#resultstrip").inner_text())
        self.assertIn(VOLUME, self.page.locator("#resultstrip").inner_text())
        self.page.get_by_role("button", name="See results").click()
        self.assertIn("logical size 1.00 GiB", self.page.locator("#v-results").inner_text())

    def test_group_selection_binds_all_paths(self):
        candidate = item(1)
        entries = [{"path": VOLUME + f"Users\\Example\\Temp\\item-{i}", "sizeBytes": i,
                    "identity": f"fixture-id-{i}"} for i in range(1, 52)]
        group = {"scanId": "scan-1", "groupId": "temp", "method": "Permanent",
                 "volume": VOLUME, "paths": entries}
        ref = approval.create(self.folder, group)
        candidate.update(group=ref, catalogRow="TMP-001")
        del candidate["paths"], candidate["sizeGiB"]
        self.generate(scan([candidate]))
        self.choose(1)
        reply = self.page.locator("#reply").input_value()
        for value in ("scan-1", "temp", "51 paths", ref["sha256"], VOLUME, "method Permanent"):
            self.assertIn(value, reply)
        self.assertNotIn("item-51", reply)
        self.page.get_by_role("button", name="Candidate 1", exact=True).first.click()
        self.assertEqual(self.page.locator("#pane-d .path").count(), 50)
        self.assertIn("Largest 50 (sample)", self.page.locator("#pane-d").inner_text())
        self.assertTrue(self.page.locator("#pane-d .path").first.inner_text().endswith("item-51"))
        link = self.page.get_by_role("link", name="Review all 51 paths")
        filename = link.get_attribute("href")
        self.assertEqual(json.loads((self.folder / filename).read_bytes())["paths"], entries)

    def test_hardlink_projection_requires_all_claimants(self):
        recycled, first, alias = item(1), item(2), item(3)
        recycled["method"] = "Recycle Bin"
        for candidate in (first, alias):
            candidate["allocations"] = [{"id": "unique-allocated-data", "bytes": GIB}]
        self.generate(scan([recycled, first, alias]))
        self.choose(1)
        self.assertIn("gain 0.00 GiB", self.page.locator("#sum").inner_text())
        self.assertIn("Pending in bin (logical) 1.00 GiB", self.page.locator("#sum").inner_text())
        self.choose(2)
        self.assertIn("gain unknown", self.page.locator("#sum").inner_text())
        self.choose(3)
        self.assertIn("gain 1.00 GiB", self.page.locator("#sum").inner_text())
        self.assertIn("projected 11.0 GiB", self.page.locator("#gtext").inner_text())

    def test_recycled_parent_and_child_cannot_inflate_pending_size(self):
        parent, child = item(1, "tree"), item(2, "tree\\cache")
        parent["method"] = child["method"] = "Recycle Bin"
        self.generate(scan([parent, child]), success=False)

    def test_unpreviewed_group_overlap_is_withheld(self):
        candidates = []
        for number in (1, 2):
            entries = [{"path": VOLUME + f"Users\\Example\\Temp\\{number}-{i}", "sizeBytes": i + 1,
                        "identity": f"{number}-{i}"} for i in range(50)]
            entries.append({"path": VOLUME + "Users\\Example\\Temp\\overlap", "sizeBytes": 0,
                            "identity": "overlap"})
            group = {"scanId": "scan-1", "groupId": f"temp-{number}", "method": "Permanent",
                     "volume": VOLUME, "paths": entries}
            candidate = item(number)
            candidate.update(group=approval.create(self.folder, group), catalogRow="TMP-001")
            candidates.append(candidate)
        self.generate(scan(candidates), success=False)

    def test_posix_path_and_platform_policy(self):
        data = scan([item(1)])
        data.update(platform="linux", volume="/")
        data["items"][0].update(volume="/", paths=[{"path": "/home/fixture/cache", "sizeGiB": 1}])
        self.generate(data)
        self.page.get_by_role("button", name="Held back 1").click()
        self.assertEqual(self.page.locator("#addr").inner_text(), "/home/fixture/cache")
        self.assertIn("/home/fixture/cache", self.page.locator("#tree").inner_text())
        self.assertEqual(self.page.locator("#clearlist input").count(), 0)

    def test_conflicting_methods_make_projection_unknown(self):
        parent, child = item(1), item(2)
        parent["allocations"] = [{"id": "cache", "bytes": GIB}]
        child["method"] = "Recycle Bin"
        child["allocations"] = [{"id": "cache", "bytes": GIB}]
        self.generate(scan([parent, child]))
        self.choose(1)
        self.choose(2)
        self.assertIn("gain unknown", self.page.locator("#sum").inner_text())
        self.assertIn("projection unknown", self.page.locator("#gtext").inner_text())

    def test_mixed_volumes_withheld(self):
        data = scan([item(1)])
        data["items"][0]["volume"] = "C:\\"
        self.generate(data, success=False)

    def test_modified_sidecar_withheld(self):
        entry = {"path": VOLUME + "Users\\Example\\Temp\\file", "sizeBytes": 1, "identity": "id"}
        group = {"scanId": "scan-1", "groupId": "temp", "method": "Permanent",
                 "volume": VOLUME, "paths": [entry]}
        candidate = item(1)
        candidate["group"] = approval.create(self.folder, group)
        path = approval.sidecar(self.folder, candidate["group"])
        path.write_bytes(path.read_bytes() + b" ")
        self.generate(scan([candidate]), success=False)


if __name__ == "__main__":
    unittest.main()
