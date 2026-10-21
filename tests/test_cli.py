from __future__ import annotations

import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import cli
import factory


def make_project(path: Path, config: dict | str) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    content = config if isinstance(config, str) else json.dumps(config)
    (path / "factory.config.json").write_text(content, encoding="utf-8")
    (path / ".gitignore").write_text(".factory/\n", encoding="utf-8")
    subprocess.run(["git", "init", "--quiet"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Factory Test"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "factory@example.test"], cwd=path, check=True)
    subprocess.run(["git", "add", "-A"], cwd=path, check=True)
    subprocess.run(["git", "commit", "--quiet", "-m", "initial"], cwd=path, check=True)
    return path


def valid_config(marker: str) -> dict:
    config = json.loads((ROOT / "factory.config.json").read_text(encoding="utf-8"))
    config["test_marker"] = marker
    for gate in config["required_gates"]:
        config["commands"][gate] = [["python", "-c", "print('configured')"]]
    return config


def make_directory_junction(target: Path, link: Path) -> None:
    try:
        os.symlink(target, link, target_is_directory=True)
    except OSError:
        if os.name != "nt":
            raise
        junction_env = os.environ.copy()
        junction_env["FACTORY_TEST_LINK"] = str(link)
        junction_env["FACTORY_TEST_TARGET"] = str(target)
        result = subprocess.run(
            ["pwsh", "-NoLogo", "-NoProfile", "-Command",
             "New-Item -ItemType Junction -Path $env:FACTORY_TEST_LINK -Target $env:FACTORY_TEST_TARGET | Out-Null"],
            check=False, capture_output=True, text=True, env=junction_env,
        )
        if result.returncode:
            raise AssertionError(f"could not create Windows junction: {result.stderr}")


class CliRunTests(unittest.TestCase):
    def test_run_argument_boundaries(self):
        project = Path("chosen project")
        idea = "quotes ' and \" ; $(touch marker)\nUnicode: \u96ea"
        forwarded = [
            "--idea", idea, "--project", str(project), "--config", "cfg path.json",
            "--publish-pr", "--base", "feature/base", "--dry-run",
        ]
        with patch.object(factory, "main", return_value=0) as supervisor:
            self.assertEqual(cli.main(["run", *forwarded]), 0)
        supervisor.assert_called_once_with(forwarded)

    def test_run_exit_codes(self):
        for code in (0, 2, 130):
            with self.subTest(code=code), patch.object(factory, "main", return_value=code):
                self.assertEqual(cli.main(["run", "--idea", "request"]), code)

    def test_project_config_default_from_foreign_cwd(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            project = make_project(base / "consumer project \u96ea", valid_config("target"))
            self.assertTrue((project / "factory.config.json").is_file())
            self.assertEqual(factory.canonical_checkout(project), project.resolve())
            foreign = base / "unrelated"
            foreign.mkdir()
            previous = Path.cwd()
            try:
                os.chdir(foreign)
                with patch.object(factory, "do_work", return_value=0) as work, \
                     patch.object(factory, "register_cli_run", wraps=factory.register_cli_run) as register:
                    self.assertEqual(factory.main(["--idea", "dry run", "--project", str(project), "--dry-run"]), 0)
            finally:
                os.chdir(previous)
            self.assertEqual(work.call_args.args[2]["test_marker"], "target")
            self.assertEqual(Path(register.call_args.args[0]), project / ".factory" / "dashboard.sqlite3")
            self.assertTrue((project / ".factory" / "dashboard.sqlite3").is_file())

    def test_installed_style_cli_supports_unicode_checkout_with_legacy_console_encoding(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            project = make_project(base / "consumer project \u96ea", valid_config("unicode"))
            foreign = base / "unrelated"
            foreign.mkdir()
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "cp1252"
            env["PYTHONUTF8"] = "0"
            result = subprocess.run(
                [
                    sys.executable, str(ROOT / "cli.py"), "run", "--idea", "dry run",
                    "--project", str(project), "--dry-run",
                ],
                cwd=foreign,
                env=env,
                text=True,
                encoding="utf-8",
                capture_output=True,
                timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("DRY RUN:", result.stdout)
            self.assertIn("consumer project \u96ea", result.stdout)
            self.assertFalse((project / ".factory" / "active-run.json").exists())

    def test_two_projects_do_not_share_cli_state(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            projects = [
                make_project(base / "one", valid_config("one")),
                make_project(base / "two", valid_config("two")),
            ]
            with patch.object(factory, "do_work", return_value=0) as work, \
                 patch.object(factory, "register_cli_run", wraps=factory.register_cli_run) as register:
                for project in projects:
                    self.assertEqual(factory.main([
                        "--idea", project.name, "--project", str(project), "--dry-run",
                    ]), 0)
            event_dbs = [Path(call.args[0]) for call in register.call_args_list]
            self.assertEqual(event_dbs, [p / ".factory" / "dashboard.sqlite3" for p in projects])
            self.assertEqual([call.args[2]["test_marker"] for call in work.call_args_list], ["one", "two"])

    def test_invalid_project_config_returns_blocked_two_without_traceback(self):
        with tempfile.TemporaryDirectory() as temp:
            project = make_project(Path(temp) / "invalid", "{not json")
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                result = factory.main(["--idea", "request", "--project", str(project), "--dry-run"])
            self.assertEqual(result, 2)
            self.assertIn("BLOCKED:", stderr.getvalue())
            self.assertNotIn("Traceback", stderr.getvalue())

    def test_malformed_nested_config_blocks_before_claim_and_next_run_succeeds(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            project = make_project(base / "invalid nested", valid_config("nested"))
            bad_config = base / "bad-config.json"
            bad_config.write_text(json.dumps({"providers": None}), encoding="utf-8")
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr), \
                 patch.object(factory, "register_cli_run", wraps=factory.register_cli_run) as register:
                result = factory.main([
                    "--idea", "request", "--project", str(project), "--config", str(bad_config), "--dry-run",
                ])
            self.assertEqual(result, 2)
            self.assertIn("BLOCKED:", stderr.getvalue())
            self.assertNotIn("Traceback", stderr.getvalue())
            register.assert_not_called()
            self.assertFalse((project / ".factory" / "active-run.json").exists())

            with patch.object(factory, "do_work", return_value=0):
                self.assertEqual(factory.main([
                    "--idea", "valid request", "--project", str(project), "--dry-run",
                ]), 0)
            self.assertFalse((project / ".factory" / "active-run.json").exists())

    def test_factory_junction_is_rejected_before_external_state_write(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            project = make_project(base / "junction target", valid_config("junction"))
            outside = base / "external state"
            outside.mkdir()
            link = project / ".factory"
            link_created = False
            try:
                make_directory_junction(outside, link)
                link_created = True

                stderr = io.StringIO()
                with contextlib.redirect_stderr(stderr), \
                     patch.object(factory, "register_cli_run", wraps=factory.register_cli_run) as register:
                    result_code = factory.main([
                        "--idea", "safe request", "--project", str(project), "--dry-run",
                    ])
                self.assertEqual(result_code, 2)
                self.assertIn("BLOCKED:", stderr.getvalue())
                self.assertNotIn("Traceback", stderr.getvalue())
                register.assert_not_called()
                self.assertEqual(list(outside.iterdir()), [])
                self.assertFalse((outside / "dashboard.sqlite3").exists())
                self.assertFalse((link / "active-run.json").exists())

                if link.is_symlink():
                    link.unlink()
                elif link.exists():
                    link.rmdir()
                link_created = False
                with patch.object(factory, "do_work", return_value=0):
                    self.assertEqual(factory.main([
                        "--idea", "valid request", "--project", str(project), "--dry-run",
                    ]), 0)
                self.assertTrue((project / ".factory" / "dashboard.sqlite3").is_file())
                self.assertFalse((project / ".factory" / "active-run.json").exists())
            finally:
                if link_created:
                    if link.is_symlink():
                        link.unlink()
                    elif link.exists():
                        link.rmdir()

    def test_descendant_factory_state_escapes_are_rejected_before_registration(self):
        for child in ("runs", "dashboard.sqlite3"):
            with self.subTest(path=child), tempfile.TemporaryDirectory() as temp:
                base = Path(temp)
                project = make_project(base / "descendant target", valid_config(child))
                factory_state = project / ".factory"
                factory_state.mkdir()
                outside = base / "external state"
                outside.mkdir()
                sentinel = outside / "sentinel.txt"
                sentinel.write_text("must remain unchanged", encoding="utf-8")
                link = factory_state / child
                make_directory_junction(outside, link)

                stderr = io.StringIO()
                with contextlib.redirect_stderr(stderr), \
                     patch.object(factory, "register_cli_run", wraps=factory.register_cli_run) as register:
                    result = factory.main([
                        "--idea", "safe request", "--project", str(project), "--dry-run",
                    ])
                self.assertEqual(result, 2)
                self.assertIn("BLOCKED:", stderr.getvalue())
                self.assertNotIn("Traceback", stderr.getvalue())
                register.assert_not_called()
                self.assertEqual(sentinel.read_text(encoding="utf-8"), "must remain unchanged")
                self.assertEqual(sorted(p.name for p in outside.iterdir()), ["sentinel.txt"])
                self.assertFalse((factory_state / "active-run.json").exists())

                if link.is_symlink():
                    link.unlink()
                elif link.exists():
                    link.rmdir()
                with patch.object(factory, "do_work", return_value=0):
                    self.assertEqual(factory.main([
                        "--idea", "valid request", "--project", str(project), "--dry-run",
                    ]), 0)
                self.assertTrue((project / ".factory" / "dashboard.sqlite3").is_file())
                self.assertFalse((project / ".factory" / "active-run.json").exists())

    def test_explicit_external_dashboard_database_remains_supported(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            project = make_project(base / "dashboard target", valid_config("handoff"))
            external_db = base / "dashboard handoff" / "events.sqlite3"
            with patch.object(factory, "do_work", return_value=0):
                self.assertEqual(factory.main([
                    "--idea", "dashboard request", "--project", str(project),
                    "--event-db", str(external_db), "--dry-run",
                ]), 0)
            self.assertTrue(external_db.is_file())
            self.assertFalse((project / ".factory" / "dashboard.sqlite3").exists())
            self.assertFalse((project / ".factory" / "active-run.json").exists())

    def test_readonly_package_installation_uses_project_state(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            runtime = base / "installed package"
            runtime.mkdir()
            for rel in ("factory.py", "skillctl.py", "POLICY.md"):
                shutil.copy2(ROOT / rel, runtime / rel)
            shutil.copytree(ROOT / "roles", runtime / "roles")
            shutil.copytree(ROOT / "skills", runtime / "skills")
            runtime_before = {
                p.relative_to(runtime): p.read_bytes()
                for p in runtime.rglob("*") if p.is_file()
            }
            project = make_project(base / "consumer \u96ea", valid_config("readonly"))
            self.assertTrue((project / "factory.config.json").is_file())
            self.assertEqual(factory.canonical_checkout(project), project.resolve())
            with patch.object(factory, "ROOT", runtime):
                result = factory.main(["--idea", "safe dry run", "--project", str(project), "--dry-run"])
            self.assertEqual(result, 0)
            self.assertFalse((runtime / ".factory").exists())
            self.assertEqual(runtime_before, {
                p.relative_to(runtime): p.read_bytes()
                for p in runtime.rglob("*") if p.is_file()
            })
            self.assertTrue((project / ".factory" / "dashboard.sqlite3").is_file())

    def test_dashboard_handoff_flags_are_forwarded(self):
        args = [
            "--idea", "dashboard request", "--project", "consumer", "--config", "custom.json",
            "--event-db", "dashboard.sqlite3", "--run-id", "stable-id",
            "--queue-token", "opaque-token", "--wait-for-lock",
        ]
        with patch.object(factory, "main", return_value=0) as supervisor:
            self.assertEqual(cli.main(["run", *args]), 0)
        supervisor.assert_called_once_with(args)


if __name__ == "__main__":
    unittest.main()
