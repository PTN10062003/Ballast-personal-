"""Generate an offline report from a measured scan and its adjacent group manifests."""
import argparse
import json
import os
from pathlib import Path

from approval import group_preview, validate_disjoint_items

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "dashboard" / "ballast-dashboard.html"
DATA_TAG = '<script type="application/json" id="ballast-data">'


def generate(data, output):
    if data.get("schema") != 2:
        raise ValueError("Expected report schema 2")
    policy = json.loads((ROOT / "plugin/policy.json").read_bytes())
    groups = validate_disjoint_items(data, output.parent, policy)
    for item in data["items"]:
        if "group" not in item:
            continue
        item.update(group_preview(groups[item["group"]["groupId"]]))

    template = TEMPLATE.read_text(encoding="utf-8")
    if template.count(DATA_TAG) != 1:
        raise ValueError("Expected one report data block")
    prefix, body = template.split(DATA_TAG)
    _, end_tag, suffix = body.partition("</script>")
    if not end_tag:
        raise ValueError("Incomplete report template")
    serialized = json.dumps(data, ensure_ascii=False, allow_nan=False).replace("<", r"\u003c")
    report = prefix + DATA_TAG + "\n" + serialized + "\n" + end_tag + suffix
    with open(output, "x", encoding="utf-8", newline="\n",
              opener=lambda path, flags: os.open(path, flags, 0o600)) as stream:
        stream.write(report)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scan", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    try:
        generate(json.loads(args.scan.read_bytes()), args.output)
    except (OSError, TypeError, KeyError, ValueError) as error:
        parser.exit(1, f"Report withheld: {error}\n")


if __name__ == "__main__":
    main()
