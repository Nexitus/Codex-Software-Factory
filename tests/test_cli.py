from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import cli
import factory
from app.events import emit as emit_event
from app.events import event_context, register_cli_run


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
                check=False, cwd=foreign,
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


def add_event_run(project: Path, run_id: str, supervisor_id: str | None,
                  events: list[tuple[str, dict]], report: dict | None = None) -> Path:
    database = project / ".factory" / "dashboard.sqlite3"
    register_cli_run(database, run_id, project, run_id, os.getpid(), None)
    with event_context(database, run_id):
        for event_type, data in events:
            emit_event(event_type, data)
    if report is not None and supervisor_id is not None:
        run_dir = project / ".factory" / "runs" / supervisor_id
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "DELIVERY.json").write_text(json.dumps(report), encoding="utf-8")
    return database


class CliDoctorStatusTests(unittest.TestCase):
    def test_doctor_missing_gate_commands(self):
        with tempfile.TemporaryDirectory() as temp:
            project = make_project(Path(temp) / "consumer", valid_config("missing-gate"))
            config_path = project / "factory.config.json"
            config = json.loads(config_path.read_text(encoding="utf-8"))
            config["commands"][config["required_gates"][0]] = []
            config_path.write_text(json.dumps(config), encoding="utf-8")

            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                result = cli.doctor(project)

            self.assertEqual(result, 2)
            self.assertIn(config["required_gates"][0], output.getvalue())
            self.assertIn("nonempty list", output.getvalue().lower())

    def test_doctor_missing_cli(self):
        with tempfile.TemporaryDirectory() as temp:
            project = make_project(Path(temp) / "consumer", valid_config("missing-cli"))
            original_which = shutil.which

            def which(command, *args, **kwargs):
                return None if command == "codex" else original_which(command, *args, **kwargs)

            output = io.StringIO()
            with patch.object(cli.shutil, "which", side_effect=which), contextlib.redirect_stdout(output):
                result = cli.doctor(project)

            self.assertEqual(result, 2)
            self.assertIn("codex", output.getvalue().lower())

    def test_doctor_uses_explicit_config(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            project = make_project(base / "consumer", "{not json")
            config = base / "selected config.json"
            config.write_text(json.dumps(valid_config("selected")), encoding="utf-8")
            output = io.StringIO()
            with patch.object(cli.shutil, "which", return_value="available"), contextlib.redirect_stdout(output):
                result = cli.doctor(project, config)
            self.assertEqual(result, 0)
            self.assertIn(str(config), output.getvalue())

    def test_doctor_never_invokes_agents_or_gates(self):
        with tempfile.TemporaryDirectory() as temp:
            project = make_project(Path(temp) / "consumer", valid_config("no-execution"))
            output = io.StringIO()
            with patch.object(cli.factory, "do_work", side_effect=AssertionError("gate or workflow executed")), \
                 patch.object(cli.factory, "execute_agent", side_effect=AssertionError("agent executed")), \
                 patch.object(cli.shutil, "which", return_value="available"), \
                 contextlib.redirect_stdout(output):
                self.assertEqual(cli.doctor(project), 0)

            self.assertIn("temporary probe created and removed", output.getvalue().lower())
            self.assertFalse((project / ".factory").exists())
            self.assertFalse((project / ".factory" / "dashboard.sqlite3").exists())

    def test_doctor_preserves_preexisting_probe_name_on_exclusive_create_collision(self):
        with tempfile.TemporaryDirectory() as temp:
            project = make_project(Path(temp) / "consumer", valid_config("probe-collision"))
            probe_dir = project / ".factory" / "runs"
            probe_dir.mkdir(parents=True)
            existing = probe_dir / ".doctor-probe-fixed"
            existing.write_text("owned by another process", encoding="utf-8")
            fixed_uuid = type("FixedUUID", (), {"hex": "fixed"})()

            with patch.object(cli.uuid, "uuid4", return_value=fixed_uuid):
                error = cli._probe_state(project)

            self.assertIsNotNone(error)
            self.assertEqual(existing.read_text(encoding="utf-8"), "owned by another process")

    def test_doctor_rejects_external_state_link_without_writing_outside(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            project = make_project(base / "consumer", valid_config("doctor-link"))
            outside = base / "external state"
            outside.mkdir()
            link = project / ".factory"
            link_created = False
            try:
                make_directory_junction(outside, link)
                link_created = True
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    result = cli.doctor(project)
                self.assertEqual(result, 2)
                self.assertEqual(list(outside.iterdir()), [])
                self.assertIn("state", output.getvalue().lower())
            finally:
                if link_created:
                    if link.is_symlink():
                        link.unlink()
                    elif link.exists():
                        link.rmdir()

    def test_no_command_prints_help(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = cli.main([])
        self.assertEqual(result, 0)
        self.assertIn("usage:", output.getvalue().lower())

    def test_status_empty_and_unicode_path_from_foreign_cwd(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            project = make_project(base / "consumer project \u96ea", valid_config("empty"))
            foreign = base / "unrelated"
            foreign.mkdir()
            previous = Path.cwd()
            output = io.StringIO()
            try:
                os.chdir(foreign)
                with contextlib.redirect_stdout(output):
                    result = cli.main(["status", "--project", str(project)])
            finally:
                os.chdir(previous)
            self.assertEqual(result, 0)
            self.assertIn("No runs", output.getvalue())
            self.assertIn("consumer project \u96ea", output.getvalue())
            self.assertFalse((project / ".factory").exists())

    def test_status_unicode_path_survives_legacy_console_encoding(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            project = make_project(base / "consumer project \u96ea", valid_config("console"))
            foreign = base / "unrelated"
            foreign.mkdir()
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "cp1252"
            env["PYTHONUTF8"] = "0"
            result = subprocess.run(
                [sys.executable, str(ROOT / "cli.py"), "status", "--project", str(project)],
                check=False, cwd=foreign, env=env, text=True, encoding="utf-8", capture_output=True, timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("consumer project \u96ea", result.stdout)

    def test_status_latest_partial_run_does_not_reuse_older_success(self):
        with tempfile.TemporaryDirectory() as temp:
            project = make_project(Path(temp) / "consumer", valid_config("latest-partial"))
            older_id, older_supervisor = "older-success", "20261021T100000000000Z"
            add_event_run(
                project, older_id, older_supervisor,
                [("run_started", {"supervisor_run_id": older_supervisor}),
                 ("delivery_verified", {"supervisor_run_id": older_supervisor,
                                         "delivery_status": "verified_candidate"}),
                 ("run_completed", {"delivery_status": "verified_candidate"})],
                {"status": "verified_candidate"},
            )
            latest_id, latest_supervisor = "latest-partial", "20261021T100100000000Z"
            add_event_run(
                project, latest_id, latest_supervisor,
                [("run_started", {"supervisor_run_id": latest_supervisor})],
            )

            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                result = cli.status(project)

            self.assertEqual(result, 0)
            self.assertIn(f"Run ID: {latest_id}", output.getvalue())
            self.assertIn("State: running", output.getvalue())
            self.assertNotIn("State: verified candidate", output.getvalue())
            self.assertIn("dashboard.sqlite3", output.getvalue())

    def test_status_newer_filesystem_run_supersedes_older_database_candidate(self):
        with tempfile.TemporaryDirectory() as temp:
            project = make_project(Path(temp) / "consumer", valid_config("newer-filesystem"))
            older_id, older_supervisor = "older-success", "20261021T100000000000Z"
            add_event_run(
                project, older_id, older_supervisor,
                [("run_started", {"supervisor_run_id": older_supervisor}),
                 ("delivery_verified", {"supervisor_run_id": older_supervisor,
                                         "delivery_status": "verified_candidate"}),
                 ("run_completed", {"delivery_status": "verified_candidate"})],
                {"status": "verified_candidate"},
            )
            newer_supervisor = "20261021T100100000000Z"
            (project / ".factory" / "runs" / newer_supervisor).mkdir()

            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                result = cli.status(project)

            self.assertEqual(result, 2)
            self.assertIn(f"Run ID: {newer_supervisor}", output.getvalue())
            self.assertIn("State: missing evidence", output.getvalue())
            self.assertNotIn("State: verified candidate", output.getvalue())
            self.assertIn(newer_supervisor, output.getvalue())

    def test_status_legacy_dry_run_report_is_preflight(self):
        with tempfile.TemporaryDirectory() as temp:
            project = make_project(Path(temp) / "consumer", valid_config("legacy-preflight"))
            supervisor_id = "20261021T100100000000Z"
            run_dir = project / ".factory" / "runs" / supervisor_id
            run_dir.mkdir(parents=True)
            dry_run = {
                "planned_roles": ["planner", "build_orchestrator", "builder"],
                "required_gates": ["lint", "tests"],
                "note": "No agents or gate commands were executed",
            }
            (run_dir / "dry-run.json").write_text(json.dumps(dry_run), encoding="utf-8")

            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                result = cli.status(project)

            self.assertEqual(result, 0)
            self.assertIn(f"Run ID: {supervisor_id}", output.getvalue())
            self.assertIn("State: preflight", output.getvalue())
            self.assertIn("dry-run.json", output.getvalue())

    def test_status_reports_preflight_running_interrupted_blocked_verified_and_malformed(self):
        cases = (
            ("preflight", [("run_started", {}), ("run_completed", {"delivery_status": "dry_run"})],
             None, 0, "preflight"),
            ("running", [("run_started", {})], None, 0, "running"),
            ("interrupted", [("run_started", {}), ("run_interrupted", {})], None, 0, "interrupted"),
            ("blocked", [("run_started", {}), ("run_blocked", {}),
                          ("run_completed", {"delivery_status": "blocked"})],
             {"status": "blocked"}, 0, "blocked"),
            ("verified", [("run_started", {}), ("delivery_verified", {"delivery_status": "verified_candidate"}),
                          ("run_completed", {"delivery_status": "verified_candidate"})],
             {"status": "verified_candidate"}, 0, "verified candidate"),
            ("malformed", [("run_started", {}), ("delivery_verified", {"delivery_status": "verified_candidate"}),
                           ("run_completed", {"delivery_status": "verified_candidate"})],
             "{broken json", 2, "malformed"),
        )
        for name, events, report, expected_code, expected_state in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temp:
                project = make_project(Path(temp) / "consumer", valid_config(name))
                supervisor_id = f"run-{name}"
                database = project / ".factory" / "dashboard.sqlite3"
                run_id = name
                register_cli_run(database, run_id, project, run_id, os.getpid(), None)
                with event_context(database, run_id):
                    for event_type, data in events:
                        if event_type in ("run_started", "delivery_verified"):
                            data = {**data, "supervisor_run_id": supervisor_id}
                        emit_event(event_type, data)
                if report is not None:
                    run_dir = project / ".factory" / "runs" / supervisor_id
                    run_dir.mkdir(parents=True, exist_ok=True)
                    content = report if isinstance(report, str) else json.dumps(report)
                    (run_dir / "DELIVERY.json").write_text(content, encoding="utf-8")
                elif name == "preflight":
                    run_dir = project / ".factory" / "runs" / supervisor_id
                    run_dir.mkdir(parents=True, exist_ok=True)
                    (run_dir / "dry-run.json").write_text("{}", encoding="utf-8")

                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    result = cli.status(project)

                self.assertEqual(result, expected_code)
                self.assertIn(f"State: {expected_state}", output.getvalue())
                self.assertIn(run_id, output.getvalue())

    def test_status_conflicting_events_never_report_verified(self):
        with tempfile.TemporaryDirectory() as temp:
            project = make_project(Path(temp) / "consumer", valid_config("conflict"))
            supervisor_id = "run-conflict"
            add_event_run(
                project, "conflict", supervisor_id,
                [("run_started", {"supervisor_run_id": supervisor_id}),
                 ("delivery_verified", {"supervisor_run_id": supervisor_id,
                                         "delivery_status": "verified_candidate"}),
                 ("run_blocked", {"supervisor_run_id": supervisor_id}),
                 ("run_completed", {"delivery_status": "blocked"})],
                {"status": "verified_candidate"},
            )

            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                result = cli.status(project)

            self.assertEqual(result, 2)
            self.assertIn("State: malformed", output.getvalue())
            self.assertNotIn("State: verified candidate", output.getvalue())

    def test_status_requires_delivery_report_for_verified_event(self):
        with tempfile.TemporaryDirectory() as temp:
            project = make_project(Path(temp) / "consumer", valid_config("missing-report"))
            supervisor_id = "run-missing-report"
            add_event_run(
                project, "missing-report", supervisor_id,
                [("run_started", {"supervisor_run_id": supervisor_id}),
                 ("delivery_verified", {"supervisor_run_id": supervisor_id,
                                         "delivery_status": "verified_candidate"}),
                 ("run_completed", {"delivery_status": "verified_candidate"})],
            )
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                result = cli.status(project)
            self.assertEqual(result, 2)
            self.assertIn("State: missing evidence", output.getvalue())
            self.assertNotIn("State: verified candidate", output.getvalue())

    def test_status_accepts_blocked_error_report(self):
        with tempfile.TemporaryDirectory() as temp:
            project = make_project(Path(temp) / "consumer", valid_config("error-report"))
            supervisor_id = "run-error-report"
            database = project / ".factory" / "dashboard.sqlite3"
            register_cli_run(database, "error-report", project, "error-report", os.getpid(), None)
            with event_context(database, "error-report"):
                emit_event("run_started", {"supervisor_run_id": supervisor_id})
                emit_event("run_blocked", {"supervisor_run_id": supervisor_id})
                emit_event("run_completed", {"delivery_status": "blocked"})
            run_dir = project / ".factory" / "runs" / supervisor_id
            run_dir.mkdir(parents=True)
            (run_dir / "ERROR.json").write_text(json.dumps({"status": "blocked"}), encoding="utf-8")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                result = cli.status(project)
            self.assertEqual(result, 0)
            self.assertIn("State: blocked", output.getvalue())
            self.assertIn("ERROR.json", output.getvalue())

    def test_status_legacy_reports_without_database_are_not_false_success(self):
        with tempfile.TemporaryDirectory() as temp:
            project = make_project(Path(temp) / "consumer", valid_config("legacy"))
            run_dir = project / ".factory" / "runs" / "legacy-run"
            run_dir.mkdir(parents=True)
            (run_dir / "DELIVERY.json").write_text(
                json.dumps({"status": "verified_candidate"}), encoding="utf-8",
            )
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                result = cli.status(project)
            self.assertEqual(result, 2)
            self.assertIn("State: missing evidence", output.getvalue())
            self.assertNotIn("State: verified candidate", output.getvalue())

    def test_status_does_not_create_or_write_event_database(self):
        with tempfile.TemporaryDirectory() as temp:
            project = make_project(Path(temp) / "consumer", valid_config("readonly"))
            database = project / ".factory" / "dashboard.sqlite3"
            database.parent.mkdir()
            database.write_bytes(b"not a database")
            before = database.read_bytes()
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                result = cli.status(project)
            self.assertEqual(result, 2)
            self.assertIn("State: malformed", output.getvalue())
            self.assertEqual(database.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
