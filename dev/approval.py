"""Create or check a group manifest in a private report directory. No file operations on candidates."""
import argparse
import hashlib
import json
import os
import re
import unicodedata
from pathlib import Path, PurePosixPath, PureWindowsPath

CONTEXT = ("scanId", "groupId", "volume", "method")


def check_id(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_-]{0,63}", value):
        raise ValueError("Invalid scan or group identifier")
    return value


def validate_volume(volume, platform):
    if (not isinstance(volume, str) or platform not in ("windows", "macos", "linux")
            or any(unicodedata.category(c) in ("Cc", "Cf") for c in volume)):
        raise ValueError("Unknown volume or platform")
    if platform == "windows":
        if not re.fullmatch(r"[A-Z]:\\", volume):
            raise ValueError("Expected a drive root")
        return PureWindowsPath(volume)
    root = PurePosixPath(volume)
    if root.anchor != "/" or ".." in root.parts or str(root) != volume:
        raise ValueError("Expected an absolute mount point")
    return root


def validate_paths(volume, names):
    windows = bool(re.fullmatch(r"[A-Z]:\\", volume))
    root = validate_volume(volume, "windows" if windows else "linux")
    seen = set()
    for raw in names:
        path = type(root)(raw)
        if (not path.is_relative_to(root) or path == root or raw != str(path) or ".." in path.parts
                or any(unicodedata.category(c) in ("Cc", "Cf") for c in raw)
                or (windows and any(re.search(r'[:*?"<>|]|[ .]$|~\d', p) for p in path.parts[1:]))):
            raise ValueError("Invalid path for this volume")
        if path in seen:
            raise ValueError("Duplicate path")
        seen.add(path)
    if not seen or any(parent in seen for path in seen for parent in path.parents):
        raise ValueError("Missing or overlapping paths")
    return seen


def validate(data):
    check_id(data["scanId"])
    check_id(data["groupId"])
    if data["method"] not in ("Permanent", "Recycle Bin"):
        raise ValueError("Unknown removal method")
    entries = data["paths"]
    if not isinstance(entries, list) or not entries:
        raise ValueError("Empty group")
    validate_paths(data["volume"], (entry["path"] for entry in entries))
    for entry in entries:
        if not isinstance(entry["identity"], str) or not entry["identity"].strip():
            raise ValueError("Missing scan identity")
        if type(entry["sizeBytes"]) is not int or entry["sizeBytes"] < 0:
            raise ValueError("Invalid logical size")


def binding(data, payload):
    return {**{key: data[key] for key in CONTEXT}, "count": len(data["paths"]),
            "sha256": hashlib.sha256(payload).hexdigest()}


def sidecar(directory, ref):
    return directory / (check_id(ref["scanId"]) + "-" + check_id(ref["groupId"]) + ".json")


def create(directory, data):
    validate(data)
    payload = (json.dumps(data, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
               + "\n").encode("utf-8")
    ref = binding(data, payload)
    with open(sidecar(directory, ref), "xb", opener=lambda p, f: os.open(p, f, 0o600)) as out:
        out.write(payload)
    return ref


def verify(directory, scan_id, retained, selected):
    """Return the entries from the verified bytes. Never open a path from a pasted reply."""
    if (retained != selected or retained.get("scanId") != check_id(scan_id)
            or type(selected.get("count")) is not int):
        raise ValueError("Selection does not match the current scan and reviewed group")
    payload = sidecar(directory, retained).read_bytes()
    if hashlib.sha256(payload).hexdigest() != retained["sha256"]:
        raise ValueError("Manifest bytes have changed")
    data = json.loads(payload)
    validate(data)
    if binding(data, payload) != retained:
        raise ValueError("Manifest context or count differs")
    return data["paths"]


def group_preview(entries):
    sample = sorted(entries, key=lambda entry: (-entry["sizeBytes"], entry["path"]))[:50]
    return {"sizeGiB": sum(entry["sizeBytes"] for entry in entries) / 2**30,
            "paths": [{"path": entry["path"], "sizeGiB": entry["sizeBytes"] / 2**30} for entry in sample]}


TIERS = ("Green", "Yellow", "Grey", "Red")


def file_tier(item, platform, policy):
    """Apply the file decision table without promoting any supplied tier."""
    row = item.get("catalogRow", "")
    tier = item.get("tier")
    caps = [tier if tier in TIERS else "Grey", policy["makers"].get(item.get("maker"), "Grey"),
            policy["fileRows"].get(row, "Grey")]
    method = item.get("method")
    if (platform != "windows" or method not in ("Permanent", "Recycle Bin")
            or (row.startswith("TMP-") and method != "Permanent")):
        caps.append("Grey")
    evidence = item.get("evidence", [])
    if not isinstance(evidence, list):
        evidence = []
    for check, states in policy["checks"].items():
        records = [e for e in evidence if isinstance(e, dict) and e.get("id") == check]
        if len(records) != 1:
            caps.append("Grey")
        for record in records:
            caps.append(states.get(record.get("state"), "Grey"))
            if not isinstance(record.get("text"), str) or not record["text"].strip():
                caps.append("Grey")
    return max(caps, key=TIERS.index)


def validate_disjoint_items(report, directory, policy):
    """Verify complete groups and enforce one selectable item per path or subtree."""
    if report["schema"] != 2 or not isinstance(report["items"], list) or len(report["items"]) > 500:
        raise ValueError("Unknown report format or invalid item list")
    scan = check_id(report["scanId"])
    validate_volume(report["volume"], report["platform"])
    free, total = report.get("freeGiB"), report.get("totalGiB")
    if type(free) not in (int, float) or type(total) not in (int, float) or not 0 <= free <= total <= 1e6:
        raise ValueError("Invalid free space or capacity for the named volume")
    seen = set()
    groups = {}
    selectable_paths = []
    held = []
    for item in report["items"]:
        number = item["id"]
        if (type(number) is not int or not 1 <= number < 2**53 or number in seen
                or item["volume"] != report["volume"] or item.get("tier") not in TIERS):
            raise ValueError("Invalid item number or volume")
        seen.add(number)
        group = item.get("group")
        if group is not None:
            if (group["groupId"] in groups or group["volume"] != item["volume"]
                    or group["method"] != item["method"]):
                raise ValueError("Group volume, method or ID differs from the review record")
            entries = verify(directory, scan, group, group)
            groups[group["groupId"]] = entries
        else:
            entries = item["paths"]
            if not isinstance(entries, list) or not 1 <= len(entries) <= 50:
                raise ValueError("Expected 1 to 50 exact paths or a complete group")
            sizes = [item.get("sizeGiB"), *(entry.get("sizeGiB") for entry in entries)]
            if any(type(size) not in (int, float) or not 0 <= size <= 1e6 for size in sizes):
                raise ValueError("Missing or invalid logical size")
            validate_paths(item["volume"], (entry["path"] for entry in entries))
        if file_tier(item, report["platform"], policy) in ("Green", "Yellow"):
            selectable_paths.extend(entry["path"] for entry in entries)
        else:
            held.extend(entry["path"] for entry in entries)
    if selectable_paths:
        selectable = validate_paths(report["volume"], selectable_paths)
        path_type = PureWindowsPath if report["platform"] == "windows" else PurePosixPath
        for raw in held:
            path = path_type(raw)
            if path in selectable or any(parent in selectable for parent in path.parents):
                raise ValueError("Selectable item includes a held or protected path")
    return groups


def markdown_choices(report, directory, policy):
    """The action column for the Markdown presentation. Render evidence and costs alongside it."""
    groups = validate_disjoint_items(report, directory, policy)
    lines = ["| Item | Tier | Choices |", "|---|---|---|"]
    for item in report["items"]:
        tier = file_tier(item, report["platform"], policy)
        choices = {"Red": "Keep", "Grey": "Keep / Check first"}.get(tier, "Keep / Clear")
        lines.append(f"| {item['id']} | {tier} | {choices} |")
    for item in report["items"]:
        if item.get("group") is None:
            continue
        group = item["group"]
        preview = group_preview(groups[group["groupId"]])
        link = sidecar(directory, group).absolute().as_uri()
        lines.extend(["", f"Item {item['id']} · scan {group['scanId']} · group {group['groupId']}",
                      f"[Review all {group['count']} paths](<{link}>) · {preview['sizeGiB']:.4f} logical GiB",
                      "", f"    Volume {group['volume']} · {group['method']} · SHA-256 {group['sha256']}",
                      "", f"Largest {len(preview['paths'])} paths (sample)", ""])
        for entry in preview["paths"]:
            # Indented Markdown code renders these exact native paths as inert text.
            lines.append("    " + entry["path"])
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    make = commands.add_parser("create", help="write a new sidecar and print its binding")
    make.add_argument("directory", type=Path)
    make.add_argument("manifest", type=Path)
    check = commands.add_parser("verify", help="compare a selection with retained scan metadata")
    check.add_argument("directory", type=Path)
    check.add_argument("scan_id")
    check.add_argument("retained", type=Path)
    check.add_argument("selected", type=Path)
    choices = commands.add_parser("choices", help="produce the Markdown tier and choice columns")
    choices.add_argument("report", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "create":
            print(json.dumps(create(args.directory, json.loads(args.manifest.read_bytes()))))
        elif args.command == "choices":
            policy_file = Path(__file__).resolve().parents[1] / "plugin" / "policy.json"
            print(markdown_choices(json.loads(args.report.read_bytes()), args.report.parent,
                                   json.loads(policy_file.read_bytes())))
        else:
            entries = verify(args.directory, args.scan_id, json.loads(args.retained.read_bytes()),
                             json.loads(args.selected.read_bytes()))
            print(f"Verified {len(entries)} paths. Final approval and individual rechecks still apply.")
    except (KeyError, TypeError, ValueError, OSError) as error:
        parser.exit(1, f"Group withheld: {error}\n")


if __name__ == "__main__":
    main()
