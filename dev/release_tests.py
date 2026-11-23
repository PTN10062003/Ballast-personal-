"""Exercise the two ZIPs produced by the release workflow, using only fixtures."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from release_verify import compare, reference_files


def check_packages(source_zip, plugin_zip, tag=None):
    source = reference_files(source_zip, False)
    plugin = reference_files(plugin_zip, True)
    assert plugin == {k[7:]: v for k, v in source.items() if k.startswith("plugin/")}
    allowed = {".md", ".json", ".png"}
    assert all(Path(name).suffix in allowed or name in {"LICENSE", "NOTICE"} for name in plugin)
    assert {"AGENTS.md", "skills/ballast/SKILL.md", "cleanup.md", "permissions.md",
            "plugin.json", ".claude-plugin/plugin.json", "steps/01-preflight.md"} <= plugin.keys()
    with TemporaryDirectory() as scratch:
        base = Path(scratch)
        with ZipFile(source_zip) as archive:
            archive.extractall(base / "source")
        checkout, = (base / "source").iterdir()
        with ZipFile(plugin_zip) as archive:
            archive.extractall(base / "install")
        install, = (base / "install").iterdir()
        assert compare(source_zip, checkout) == []
        assert compare(plugin_zip, install, True) == []
        assert compare(source_zip, install, True) == []
        diagnosis_tests = Path(__file__).resolve().with_name("codex_diagnosis_tests.py")
        subprocess.run([sys.executable, "-I", "-B", str(diagnosis_tests)],
                       env={**os.environ, "BALLAST_TEST_PLUGIN": str(install)}, cwd=base, check=True)
        manifests = [json.loads((install / name).read_text(encoding="utf-8"))
                     for name in ("plugin.json", ".claude-plugin/plugin.json")]
        versions = {manifest["version"] for manifest in manifests}
        assert len(versions) == 1
        assert all(m["author"]["name"] == "PTN10062003" for m in manifests)
        if tag:
            assert versions == {tag.removeprefix("v")}, "tag must match both plugin manifests"
        # Observe child-process attempts without relying on the local Git configuration.
        git_config = checkout / ".git" / "config"
        git_config.parent.mkdir()
        git_config.write_text("[core]\n\tfsmonitor = ballast-helper-must-never-run\n")
        verifier = Path(__file__).with_name("release_verify.py").absolute()
        audit = """
import runpy, sys
def ensure_read_only(event, args):
    if event in {"subprocess.Popen", "os.system", "os.posix_spawn", "os.exec"}:
        raise AssertionError("verifier launched an external process")
sys.addaudithook(ensure_read_only)
sys.argv = sys.argv[1:]
runpy.run_path(sys.argv[0], run_name="__main__")
"""

        def check(*args):
            return subprocess.run([sys.executable, "-I", "-c", audit, str(verifier), *map(str, args)],
                                  cwd=base, env={**os.environ, "PATH": ""}, capture_output=True)

        assert check(source_zip, checkout).returncode == 0
        # Changing instructions with the original version must invalidate both routes.
        for root, ref, options in [(install, plugin_zip, ["--plugin"]), (checkout, source_zip, [])]:
            instruction = root / ("AGENTS.md" if options else "plugin/AGENTS.md")
            with instruction.open("ab") as stream:
                stream.write(b"\nEdited.\n")
            result = check(*options, ref, root)
            assert result.returncode == 1 and b"modified " in result.stderr, result.stderr
        (install / "permissions.md").unlink()
        (install / "unexpected.md").write_text("fixture")
        problems = compare(plugin_zip, install, True)
        assert "missing 'permissions.md'" in problems and "extra 'unexpected.md'" in problems
        assert not (install / ".git").exists()
    print("Source ZIP, packaged plugin, fork manifests and integrity failures passed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_zip", type=Path)
    parser.add_argument("plugin_zip", type=Path)
    parser.add_argument("--tag")
    args = parser.parse_args()
    check_packages(args.source_zip.resolve(), args.plugin_zip.resolve(), args.tag)
