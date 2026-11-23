"""Compare an inactive Ballast installation with an independently trusted ZIP.

Run a trusted copy of this script from outside the installation, with python -I.
The caller authenticates the reference archive first. No Git commands are used.
"""
import argparse
import hashlib
from pathlib import Path
import stat
import sys
import zipfile


def digest(stream):
    result = hashlib.sha256()
    for chunk in iter(lambda: stream.read(65536), b""):
        result.update(chunk)
    return result.digest()


def reference_files(archive, plugin_only):
    files = {}
    roots = set()
    with zipfile.ZipFile(archive) as source:
        for entry in source.infolist():
            parts = entry.filename.rstrip("/").split("/")
            if any(part in ("", ".", "..") or "\\" in part or ":" in part for part in parts):
                raise ValueError("invalid path in reference archive")
            roots.add(parts[0])
            if entry.is_dir():
                continue
            if len(parts) < 2 or stat.S_ISLNK(entry.external_attr >> 16):
                raise ValueError("expected ordinary files under one archive root")
            name = "/".join(parts[1:])
            if name in files:
                raise ValueError("duplicate file in reference archive")
            with source.open(entry) as stream:
                files[name] = digest(stream)
    if len(roots) != 1:
        raise ValueError("expected a single archive root")
    if plugin_only and "plugin/plugin.json" in files:
        files = {name[7:]: value for name, value in files.items() if name.startswith("plugin/")}
    manifest = "plugin.json" if plugin_only else "plugin/plugin.json"
    if "AGENTS.md" not in files or manifest not in files:
        raise ValueError("reference archive does not match selected installation type")
    return files


def ordinary(path):
    info = path.lstat()
    if getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
        raise ValueError(f"reparse point: {str(path)!a}")
    if stat.S_ISLNK(info.st_mode):
        raise ValueError(f"symbolic link: {str(path)!a}")
    return info.st_mode


def compare(archive, folder, plugin_only=False):
    expected = reference_files(archive, plugin_only)
    if not stat.S_ISDIR(ordinary(folder)):
        raise ValueError("expected an installation directory")
    differences = []
    pending = [folder]
    while pending:
        directory = pending.pop()
        for child in directory.iterdir():
            name = child.relative_to(folder).as_posix()
            if name == ".git" and not plugin_only:
                continue  # The checkout's Git metadata is neither inspected nor executed.
            mode = ordinary(child)
            if stat.S_ISDIR(mode):
                pending.append(child)
            elif not stat.S_ISREG(mode):
                raise ValueError(f"unexpected file type: {name!a}")
            elif name not in expected:
                differences.append(f"extra {name!a}")
            else:
                with child.open("rb") as stream:
                    if digest(stream) != expected.pop(name):
                        differences.append(f"modified {name!a}")
    differences.extend(f"missing {name!a}" for name in expected)
    return sorted(differences)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plugin", action="store_true", help="verify a plugin-only installation")
    parser.add_argument("reference_zip", type=Path)
    parser.add_argument("installation", type=Path)
    args = parser.parse_args()
    try:
        differences = compare(args.reference_zip, args.installation, args.plugin)
    except (OSError, ValueError, RuntimeError, zipfile.BadZipFile) as exc:
        parser.exit(1, f"Verification failed: {exc}\n")
    if differences:
        parser.exit(1, "\n".join(differences) + "\n")
    print(f"Verified file names and bytes in {str(args.installation.absolute())!a}")


if __name__ == "__main__":
    sys.exit(main())
