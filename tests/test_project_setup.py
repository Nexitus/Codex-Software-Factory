from __future__ import annotations

import contextlib
import importlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import cli


def load_project_setup():
    try:
        return importlib.import_module("project_setup")
    except ModuleNotFoundError as error:
        if error.name == "project_setup":
            raise AssertionError("project_setup.initialize is not implemented") from error
        raise


def init_git(path: Path) -> None:
    subprocess.run(["git", "init", "--quiet"], cwd=path, check=True)


def commit_git(path: Path) -> None:
    subprocess.run(["git", "-c", "user.name=Factory Test", "-c", "user.email=factory@example.test",
                    "add", "-A"], cwd=path, check=True)
    subprocess.run(["git", "-c", "user.name=Factory Test", "-c", "user.email=factory@example.test",
                    "commit", "--quiet", "--allow-empty", "-m", "initial"], cwd=path, check=True)


def ignored_factory_state(path: Path) -> bool:
    result = subprocess.run(["git", "check-ignore", "--quiet", "--", ".factory/"],
                            cwd=path, check=False)
    return result.returncode == 0


class ProjectSetupTests(unittest.TestCase):
    def test_init_minimal_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "app"
            root.mkdir()
            init_git(root)
            (root / "README.md").write_bytes(b"project readme\r\n")
            (root / "AGENTS.md").write_bytes(b"project instructions\r\n")
            (root / "CLAUDE.md").write_bytes(b"claude instructions\r\n")
            (root / ".gitignore").write_bytes(b"node_modules/\r\n")
            (root / "app").mkdir()
            (root / "app" / "keep.py").write_bytes(b"KEEP = True\r\n")
            (root / "dashboard").mkdir()
            (root / "dashboard" / "keep.html").write_bytes(b"dashboard owned by project")
            before = {name: (root / name).read_bytes() for name in
                      ("README.md", "AGENTS.md", "CLAUDE.md", ".gitignore",
                       "app/keep.py", "dashboard/keep.html")}
            needs_ignore = not ignored_factory_state(root)

            written = load_project_setup().initialize(root / "app", ["codex", "claude", "opencode"])

            config = json.loads((root / "factory.config.json").read_text(encoding="utf-8"))
            self.assertEqual(set(config["providers"]), {
                "planner", "build_orchestrator", "builder", "testing",
                "architecture", "ui", "ux", "security",
            })
            self.assertEqual(set(config["providers"].values()), {"codex"})
            self.assertEqual(config["models"], {
                "planner": "gpt-6-sol",
                "build_orchestrator": "gpt-6-sol",
                "builder": "gpt-6-luna",
                "testing": "gpt-6-luna",
                "architecture": "gpt-6-luna",
                "ui": "gpt-6-luna",
                "ux": "gpt-6-luna",
                "security": "gpt-6-luna",
            })
            self.assertEqual(config["required_gates"], ["tests", "lint", "security", "build"])
            self.assertTrue(all(commands == [] for commands in config["commands"].values()))
            self.assertEqual(config["max_review_rounds"], 3)
            self.assertEqual(config["max_agent_seconds"], 1200)
            self.assertEqual(config["max_gate_seconds"], 600)
            self.assertEqual((root / ".agents/skills/software-factory/SKILL.md").is_file(), True)
            self.assertEqual((root / ".claude/skills/software-factory/SKILL.md").is_file(), True)
            self.assertEqual({path.relative_to(root).as_posix() for path in written} >= {
                "factory.config.json",
                ".agents/skills/software-factory/SKILL.md",
                ".claude/skills/software-factory/SKILL.md",
            }, True)
            self.assertEqual((root / ".factory").exists(), False)
            self.assertEqual((root / "factory.py").exists(), False)
            self.assertEqual(set(p.name for p in (root / "app").iterdir()), {"keep.py"})
            self.assertEqual(set(p.name for p in (root / "dashboard").iterdir()), {"keep.html"})
            for name, content in before.items():
                if name != ".gitignore" or not needs_ignore:
                    self.assertEqual((root / name).read_bytes(), content)
            if needs_ignore:
                ignore_text = (root / ".gitignore").read_text(encoding="utf-8")
                self.assertIn("# >>> codex-software-factory managed >>>", ignore_text)
                self.assertIn(".factory/", ignore_text)

    def test_init_repeat_is_noop(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "repeat"
            root.mkdir()
            init_git(root)
            setup = load_project_setup()

            first = setup.initialize(root, ["codex", "claude", "opencode"])
            paths = [root / "factory.config.json",
                     root / ".agents/skills/software-factory/SKILL.md",
                     root / ".claude/skills/software-factory/SKILL.md",
                     root / ".gitignore"]
            snapshots = {path: path.read_bytes() for path in paths if path.exists()}
            second = setup.initialize(root, ["codex", "claude", "opencode"])

            self.assertTrue(first)
            self.assertEqual(second, [])
            self.assertEqual({path: path.read_bytes() for path in snapshots}, snapshots)

    def test_conflict_is_atomic(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "conflict"
            root.mkdir()
            init_git(root)
            config = root / "factory.config.json"
            config.write_bytes(b"existing user configuration\x00")
            ignore = root / ".gitignore"
            ignore.write_bytes(b"keep this ignore file\r\n")
            conflict = root / ".agents/skills/software-factory/SKILL.md"
            conflict.parent.mkdir(parents=True)
            conflict.write_bytes(b"user-edited skill\r\n")
            before = {path: path.read_bytes() for path in (config, ignore, conflict)}

            with self.assertRaisesRegex(ValueError, r"\.agents[/\\]skills[/\\]software-factory"):
                load_project_setup().initialize(root, ["codex", "claude"])

            self.assertEqual({path: path.read_bytes() for path in before}, before)
            self.assertFalse((root / ".claude").exists())

    def test_init_worktree_unicode_space_path(self) -> None:
        with tempfile.TemporaryDirectory(prefix="factory-main-") as temp:
            main = Path(temp) / "main"
            main.mkdir()
            init_git(main)
            commit_git(main)
            worktree = Path(temp) / "Prøject workspace"
            subprocess.run(["git", "worktree", "add", "--quiet", "--detach", str(worktree), "HEAD"],
                           cwd=main, check=True)
            self.assertTrue((worktree / ".git").is_file())

            written = load_project_setup().initialize(worktree, ["codex"])

            self.assertTrue((worktree / "factory.config.json").is_file())
            self.assertTrue((worktree / ".agents/skills/software-factory/SKILL.md").is_file())
            self.assertFalse((worktree / ".claude").exists())
            self.assertTrue(written)

    def test_reject_symlink_parent(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "repo"
            outside = Path(temp) / "outside"
            root.mkdir()
            outside.mkdir()
            init_git(root)
            link = root / ".agents"
            try:
                try:
                    os.symlink(outside, link, target_is_directory=True)
                except OSError:
                    if os.name != "nt":
                        raise
                    junction_env = os.environ.copy()
                    junction_env["FACTORY_TEST_LINK"] = str(link)
                    junction_env["FACTORY_TEST_TARGET"] = str(outside)
                    result = subprocess.run(
                        ["pwsh", "-NoLogo", "-NoProfile", "-Command",
                         "New-Item -ItemType Junction -Path $env:FACTORY_TEST_LINK -Target $env:FACTORY_TEST_TARGET | Out-Null"],
                        capture_output=True, text=True, env=junction_env,
                    )
                    if result.returncode:
                        self.fail(f"could not create Windows junction: {result.stderr}")
                self.assertTrue(link.is_dir())
                with self.assertRaisesRegex(ValueError, r"outside|escape|\.agents"):
                    load_project_setup().initialize(root, ["codex"])
                self.assertFalse((root / "factory.config.json").exists())
                self.assertEqual(list(outside.iterdir()), [])
            finally:
                if link.is_symlink():
                    link.unlink()
                elif link.exists():
                    link.rmdir()

    def test_select_harnesses(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "selected"
            root.mkdir()
            init_git(root)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                result = cli.main([
                    "init", "--project", str(root),
                    "--harness", "codex", "--harness", "opencode",
                ])

            self.assertEqual(result, 0, output.getvalue())
            self.assertTrue((root / ".agents/skills/software-factory/SKILL.md").is_file())
            self.assertFalse((root / ".claude").exists())
            self.assertTrue((root / "factory.config.json").is_file())

    def test_existing_config_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "custom-config"
            root.mkdir()
            init_git(root)
            config = root / "factory.config.json"
            config.write_bytes(b"{ this is deliberately user-owned config }\r\n")

            load_project_setup().initialize(root, ["claude"])

            self.assertEqual(config.read_bytes(), b"{ this is deliberately user-owned config }\r\n")

    def test_reject_non_checkout_before_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "not-a-checkout"
            root.mkdir()
            (root / "README.md").write_bytes(b"untouched")
            with self.assertRaises(ValueError):
                load_project_setup().initialize(root, ["codex"])
            self.assertEqual(list(root.iterdir()), [root / "README.md"])

    def test_io_failure_removes_only_new_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "io-failure"
            root.mkdir()
            init_git(root)
            user_file = root / "README.md"
            user_file.write_bytes(b"preserve")
            setup = load_project_setup()
            real_link = os.link
            calls = 0

            def fail_second_link(source, destination, *args, **kwargs):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError("injected link failure")
                return real_link(source, destination, *args, **kwargs)

            with patch.object(setup.os, "link", side_effect=fail_second_link):
                with self.assertRaisesRegex(OSError, "injected link failure"):
                    setup.initialize(root, ["codex", "claude"])

            self.assertEqual(user_file.read_bytes(), b"preserve")
            self.assertFalse((root / "factory.config.json").exists())
            self.assertFalse((root / ".claude").exists())
            self.assertFalse(any(root.glob(".codex-factory-init-*")))


if __name__ == "__main__":
    unittest.main()
