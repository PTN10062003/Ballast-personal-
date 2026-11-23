"""Current-scan approvals and text dashboard regression fixtures."""
import json
import tempfile
import unittest
from pathlib import Path

from approval import create, markdown_choices, sidecar, verify

POLICY = json.loads((Path(__file__).resolve().parents[1] / "plugin/policy.json").read_bytes())
VOLUME = "D:\\"
CACHE = r"D:\Users\Sample\AppData\Local\Temp"
SCAN = "sample-scan"


def candidate():
    return {"tier": "Green", "catalogRow": "TMP-001", "method": "Permanent", "maker": "High",
            "paths": [{"path": CACHE + r"\unused.tmp", "sizeGiB": 0.01}], "id": 1, "volume": VOLUME,
            "sizeGiB": 0.01,
            "evidence": [{"id": key, "state": "ok", "text": "Checked for this fixture"}
                         for key in POLICY["checks"]]}


class ReviewTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.manifest = {"scanId": SCAN, "groupId": "temp", "volume": VOLUME, "method": "Permanent",
                         "paths": [{"path": CACHE + f"\\{i}.tmp", "sizeBytes": i, "identity": f"id-{i}"}
                                   for i in range(51)]}

    def choices(self, item):
        report = self.report([item])
        return markdown_choices(report, self.directory, POLICY).splitlines()[-1]

    @staticmethod
    def report(items):
        return {"schema": 2, "scanId": SCAN, "platform": "windows", "volume": VOLUME,
                "freeGiB": 5, "totalGiB": 10, "items": items}

    def test_group_includes_the_unpreviewed_entry(self):
        ref = create(self.directory, self.manifest)
        self.assertEqual(ref["count"], 51)
        self.assertEqual(verify(self.directory, SCAN, ref, dict(ref)), self.manifest["paths"])
        group = dict(candidate(), group=ref)
        report = self.report([group])
        output = markdown_choices(report, self.directory, POLICY)
        for expected in ("Keep / Clear", "Review all 51 paths", "Largest 50 paths (sample)",
                         ref["sha256"], CACHE + r"\50.tmp"):
            self.assertIn(expected, output)
        self.assertNotIn(CACHE + r"\0.tmp", output)
        with self.assertRaises(FileExistsError):
            create(self.directory, self.manifest)

    def test_only_current_scope_can_validate(self):
        ref = create(self.directory, self.manifest)
        for field, replacement in (("scanId", "previous"), ("method", "Recycle Bin"),
                                   ("count", 50), ("volume", "C:\\"), ("groupId", "other"),
                                   ("sha256", "0" * 64)):
            with self.subTest(field=field), self.assertRaises(ValueError):
                verify(self.directory, SCAN, ref, dict(ref, **{field: replacement}))
        with self.assertRaises(ValueError):
            verify(self.directory, "another-scan", ref, ref)
        file = sidecar(self.directory, ref)
        file.write_bytes(file.read_bytes() + b"\n")
        with self.assertRaises(ValueError):
            verify(self.directory, SCAN, ref, ref)

    def test_ambiguous_or_overlapping_group_withheld(self):
        for path in (r"C:\other", CACHE, CACHE + r"\0.tmp", CACHE + r"\0.tmp\child",
                     CACHE + r"\..\other", CACHE + r"\future*"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                copy = dict(self.manifest, paths=self.manifest["paths"] + [{
                    "path": path, "sizeBytes": 1, "identity": "fixture"
                }])
                create(self.directory, copy)
        self.assertEqual(list(self.directory.iterdir()), [])

    def test_markdown_only_offers_checked_catalog_files(self):
        self.assertEqual(self.choices(candidate()), "| 1 | Yellow | Keep / Clear |")
        cases = (("E8", "missing", "Grey"), ("E2", "block", "Grey"), ("E7", "block", "Red"),
                 ("E5", "block", "Red"), ("E2", "na", "Grey"), ("E4", "duplicate", "Grey"))
        for check, state, expected in cases:
            with self.subTest(check=check, state=state):
                item = candidate()
                record = next(e for e in item["evidence"] if e["id"] == check)
                if state == "missing":
                    item["evidence"].remove(record)
                elif state == "duplicate":
                    item["evidence"].append(record)
                else:
                    record["state"] = state
                row = self.choices(item)
                self.assertIn(expected, row)
                self.assertNotIn("Clear", row)

    def test_protection_wins_even_with_other_checks_missing(self):
        item = dict(candidate(), evidence=[{"id": "E7", "state": "block", "text": "Protected"}])
        self.assertEqual(self.choices(item), "| 1 | Red | Keep |")
        for fields in ({"maker": "Low"}, {"method": "Recycle Bin"}, {"catalogRow": "LIN-001"},
                       {"tier": "Grey"}):
            self.assertNotIn("Clear", self.choices(dict(candidate(), **fields)))

    def test_reject_volume_incompatible_with_platform_even_if_empty(self):
        for platform, volume in (("windows", "/"), ("windows", "//"), ("linux", "C:\\"),
                                 ("macos", "//server")):
            report = dict(self.report([]), platform=platform, volume=volume)
            with self.subTest(report=report), self.assertRaises(ValueError):
                markdown_choices(report, self.directory, POLICY)

    def test_group_does_not_hide_overlaps_outside_its_preview(self):
        ref = create(self.directory, self.manifest)
        first = dict(candidate(), group=ref)
        second = dict(candidate(), id=2, paths=[{"path": CACHE + r"\0.tmp", "sizeGiB": 0}])
        report = self.report([first, second])
        for tier in ("Yellow", "Red"):
            second["tier"] = tier
            with self.subTest(tier=tier), self.assertRaises(ValueError):
                markdown_choices(report, self.directory, POLICY)

    def test_unmeasured_size_cannot_be_offered_in_markdown(self):
        for size in (None, -1, "12", False, float("nan")):
            with self.subTest(size=size), self.assertRaises(ValueError):
                self.choices(dict(candidate(), sizeGiB=size))


if __name__ == "__main__":
    unittest.main()
