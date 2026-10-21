from __future__ import annotations

import asyncio
import contextvars
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from httpx import ASGITransport, AsyncClient
from starlette.requests import Request

from app import server
from app.checkout_lock import CheckoutClaim, CheckoutQuarantined, checkout_lock, claim_checkout
from app.events import (add_event, assert_no_orphaned_run, connect, emit, event_context,
                       events_for, initialize, redact, register_cli_run)
from app.process_guard import process_birth, process_matches
from app.projector import project_run
import factory


def make_project(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    return path


def insert_run(db_path: Path, project: Path, *, run_id: str = "run-1", status: str = "running",
               supervisor_run_id: str | None = None, worker_pid: int = 999999,
               worker_token: str | None = "dead-process") -> None:
    now = "2026-10-21T00:00:00+00:00"
    db = connect(db_path)
    try:
        db.execute("""INSERT INTO runs(id,project_id,project_name,project_path,requirement,status,stage,
                     created_at,updated_at,queue_position,supervisor_run_id,worker_pid,worker_token)
                     VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                   (run_id, "test", "Test project", str(project.resolve()), "Test requirement", status,
                    "Planning", now, now, 0, supervisor_run_id, worker_pid, worker_token))
    finally:
        db.close()


class RedactionTests(unittest.TestCase):
    def test_redacts_auth_schemes_and_common_unlabelled_credentials(self):
        cases = (
            "Authorization: Bearer TEST_SECRET_0123456789",
            "Authorization: Basic VEVTVF9TRUNSRVQ=",
            "inline ghp_TESTGITHUBTOKEN012345678901234",
            "AWS key AKIA1234567890ABCDEF",
            "vendor key sk-0123456789abcdefghijklmno",
        )
        for value in cases:
            with self.subTest(value=value):
                result = redact(value)
                self.assertNotIn(value.split()[-1], result)
                self.assertIn("[redacted", result)

    def test_redacts_secret_dictionary_keys_and_nested_values(self):
        result = redact({"token": "TEST_TOKEN", "nested": [{"authorization": "Bearer TEST_SECRET_0123456789"}]})
        self.assertEqual(result["token"], "[redacted]")
        self.assertEqual(result["nested"][0]["authorization"], "[redacted]")

    def test_artifact_prose_redacts_snake_camel_and_environment_key_labels(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            run_dir = project / ".factory" / "runs" / "safe-run"
            run_dir.mkdir(parents=True)
            secrets = ["TEST_CLIENT_SECRET_987654", "TEST_CAMEL_SECRET_987654", "TEST_OPENAI_KEY_987654321"]
            payload = {"status": "blocked", "error": " ".join((
                f"client_secret={secrets[0]}", f"clientSecret: {secrets[1]}", f"OPENAI_API_KEY={secrets[2]}"))}
            (run_dir / "DELIVERY.json").write_text(json.dumps(payload), encoding="utf-8")
            safe = server._artifact_json({"id": "p", "name": "P", "path": str(project)}, "safe-run", "DELIVERY.json")
            serialized = json.dumps(safe)
            for secret in secrets:
                self.assertNotIn(secret, serialized)

    def test_delivery_artifacts_reject_non_object_json(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            run_dir = project / ".factory" / "runs" / "bad-report"
            run_dir.mkdir(parents=True)
            path = run_dir / "DELIVERY.json"
            for value in ([], None, "text", 42, False):
                with self.subTest(value=value):
                    path.write_text(json.dumps(value), encoding="utf-8")
                    self.assertIsNone(server._artifact_json(
                        {"id": "p", "name": "P", "path": str(project)}, "bad-report", "DELIVERY.json"))


class EventStoreTests(unittest.TestCase):
    def test_concurrent_event_writers_get_unique_persisted_global_sequences(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            project = make_project(root / "project")
            db_path = root / "events.sqlite3"
            initialize(db_path, mode="live")
            for run_id in ("left", "right"):
                register_cli_run(db_path, run_id, project, f"requirement {run_id}", os.getpid(), process_birth(os.getpid()))

            def write(run_id: str, number: int) -> None:
                with event_context(db_path, run_id, run_id):
                    emit("verification_probe", {"number": number})

            with ThreadPoolExecutor(max_workers=12) as pool:
                futures = [pool.submit(write, "left" if index % 2 else "right", index) for index in range(100)]
                for future in futures:
                    future.result()
            db = connect(db_path)
            try:
                seqs = [row[0] for row in db.execute("SELECT seq FROM events ORDER BY seq")]
            finally:
                db.close()
            self.assertEqual(len(seqs), 104)  # two initial lifecycle events per run plus 100 concurrent writes
            self.assertEqual(len(set(seqs)), len(seqs))
            self.assertEqual(seqs, sorted(seqs))
            self.assertEqual(len(events_for(db_path, "left")) + len(events_for(db_path, "right")), 104)

    def test_run_handoff_requires_unguessable_token_and_terminal_ids_cannot_be_reused(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            project = make_project(root / "project")
            db_path = root / "events.sqlite3"
            initialize(db_path, mode="live")
            now = "2026-10-21T00:00:00+00:00"
            db = connect(db_path)
            try:
                db.execute("INSERT INTO runs(id,project_id,project_name,project_path,requirement,status,stage,created_at,updated_at,queue_position,handoff_token) VALUES(?,?,?,?,?,'queued','Queue',?,?,1,?)",
                           ("queued", "test", "Test", str(project), "Need", now, now, "secret-handoff"))
            finally:
                db.close()
            with self.assertRaises(ValueError):
                register_cli_run(db_path, "queued", project, "Need", os.getpid(), "birth", "wrong-token", require_handoff=True)
            register_cli_run(db_path, "queued", project, "Need", os.getpid(), "birth", "secret-handoff", require_handoff=True)
            db = connect(db_path)
            try:
                db.execute("UPDATE runs SET status='completed' WHERE id='queued'")
            finally:
                db.close()
            with self.assertRaises(ValueError):
                register_cli_run(db_path, "queued", project, "Need", os.getpid(), "birth", "secret-handoff", require_handoff=True)

    def test_orphan_check_does_not_exempt_reused_current_run_id(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            project = make_project(root / "project")
            db_path = root / "events.sqlite3"
            initialize(db_path, mode="live")
            insert_run(db_path, project, status="orphaned")
            with self.assertRaises(RuntimeError):
                assert_no_orphaned_run(db_path, project, "run-1")

    def test_demo_database_cannot_be_reopened_live(self):
        with tempfile.TemporaryDirectory() as temp:
            db_path = Path(temp) / "events.sqlite3"
            initialize(db_path, mode="demo")
            with self.assertRaises(ValueError):
                initialize(db_path, mode="live")


class ProjectionTests(unittest.TestCase):
    @staticmethod
    def event(seq: int, kind: str, data: dict) -> dict:
        return {"id": seq, "seq": seq, "run_id": "r", "type": kind,
                "timestamp": f"2026-10-21T00:00:{seq:02d}+00:00", "data": data}

    def test_ready_requires_verified_candidate_payload_and_terminal_stage_is_stable(self):
        base = {"id": "r", "status": "queued", "stage": "Queue", "project_path": "."}
        invalid = project_run(base, [self.event(1, "run_started", {}),
                                     self.event(2, "delivery_verified", {"delivery_status": "blocked"})])
        self.assertNotEqual(invalid["stage"], "Ready")
        valid = project_run(base, [self.event(1, "run_started", {"max_rounds": 2}),
                                   self.event(2, "stage_entered", {"stage": "Review"}),
                                   self.event(3, "agent_started", {"role": "architecture", "phase": "review", "round": 1}),
                                   self.event(4, "agent_succeeded", {"role": "architecture", "phase": "review", "round": 1, "verdict": "fail"}),
                                   self.event(5, "delivery_verified", {"delivery_status": "verified_candidate"}),
                                   self.event(6, "stage_entered", {"stage": "Build"})])
        self.assertEqual((valid["status"], valid["stage"], valid["delivery_status"]),
                         ("completed", "Ready", "verified_candidate"))
        self.assertEqual(valid["agents"][0]["status"], "failed")

    def test_demo_context_is_projected_as_synthetic_plan_and_design(self):
        detail = project_run({"id": "r", "status": "queued", "stage": "Queue"}, [
            self.event(1, "run_started", {}),
            self.event(2, "demo_context", {"synthetic": True, "plan": {"synthetic": True, "acceptance_criteria": []},
                                             "design": [{"role": "architecture", "synthetic": True}]})])
        self.assertTrue(detail["demo_plan"]["synthetic"])
        self.assertEqual(detail["demo_design"][0]["role"], "architecture")


class ProcessAndRecoveryTests(unittest.TestCase):
    def test_process_birth_matches_only_the_live_process_token(self):
        token = process_birth(os.getpid())
        self.assertIsNotNone(token)
        self.assertTrue(process_matches(os.getpid(), token))
        self.assertFalse(process_matches(os.getpid(), "wrong-birth-token"))

    def test_checkout_marker_survives_until_explicit_safe_release(self):
        with tempfile.TemporaryDirectory() as temp:
            project = make_project(Path(temp) / "project")
            claim = claim_checkout(project, "run-safe", os.getpid(), process_birth(os.getpid()))
            marker = project / ".factory" / "active-run.json"
            self.assertTrue(marker.is_file())
            with self.assertRaises(CheckoutQuarantined):
                CheckoutClaim(project, "second-run", os.getpid(), process_birth(os.getpid())).acquire()
            claim.release_after_worker_exit()
            self.assertFalse(marker.exists())

    def test_checkout_os_lock_excludes_a_second_process(self):
        with tempfile.TemporaryDirectory() as temp:
            project = make_project(Path(temp) / "project")
            source_root = Path(__file__).resolve().parents[1]
            child = "\n".join((
                f"import sys; sys.path.insert(0, {str(source_root)!r})",
                "from pathlib import Path",
                "from app.checkout_lock import CheckoutBusy, checkout_lock",
                f"project = Path({str(project)!r})",
                "try:",
                "    with checkout_lock(project): pass",
                "except CheckoutBusy: raise SystemExit(3)",
                "raise SystemExit(0)",
            ))
            with checkout_lock(project):
                result = subprocess.run([os.sys.executable, "-c", child], cwd=project,
                                         capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 3, result.stderr)

    def test_recovery_keeps_live_supervisor_attached(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            project = make_project(root / "project")
            db_path = root / "events.sqlite3"
            initialize(db_path, mode="live")
            insert_run(db_path, project, worker_pid=os.getpid(), worker_token=process_birth(os.getpid()))
            queue = server.RunQueue(db_path, [{"id": "test", "name": "Test", "path": str(project)}], demo=False)
            queue._recover()
            self.assertEqual(server._run_row(db_path, "run-1")["status"], "running")
            self.assertFalse((project / ".factory" / "active-run.json").exists())
            self.assertNotIn("run_orphaned", [event["type"] for event in events_for(db_path, "run-1")])

    def test_queue_parent_does_not_overwrite_cli_registered_worker_identity(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            project = make_project(root / "project")
            (project / "factory.config.json").write_text("{}", encoding="utf-8")
            db_path = root / "events.sqlite3"
            initialize(db_path, mode="live")
            now = "2026-10-21T00:00:00+00:00"
            db = connect(db_path)
            try:
                db.execute("INSERT INTO runs(id,project_id,project_name,project_path,requirement,status,stage,created_at,updated_at,queue_position,handoff_token) VALUES(?,?,?,?,?,'starting','Queue',?,?,1,?)",
                           ("handoff-run", "test", "Test", str(project), "Need", now, now, "queue-secret"))
            finally:
                db.close()

            class ParentProcess:
                pid = os.getpid() + 900000

                @staticmethod
                def wait():
                    return 0

            queue = server.RunQueue(db_path, [{"id": "test", "name": "Test", "path": str(project)}], demo=False)

            def fake_popen(_command, **_kwargs):
                register_cli_run(db_path, "handoff-run", project, "Need", os.getpid(), process_birth(os.getpid()),
                                 "queue-secret", require_handoff=True)
                with event_context(db_path, "handoff-run", "handoff-run"):
                    emit("run_started", {"supervisor_run_id": "supervisor-run", "max_rounds": 1})
                return ParentProcess()

            with patch("app.server.subprocess.Popen", side_effect=fake_popen):
                queue._execute({"id": "handoff-run", "project_id": "test", "requirement": "Need",
                                "handoff_token": "queue-secret"})
            run = server._run_row(db_path, "handoff-run")
            self.assertEqual(run["worker_pid"], os.getpid())
            self.assertEqual(run["worker_token"], process_birth(os.getpid()))
            self.assertEqual(run["status"], "running")
            self.assertFalse((project / ".factory" / "active-run.json").exists())


    def test_non_object_reports_do_not_crash_recovery(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            project = make_project(root / "project")
            db_path = root / "events.sqlite3"
            initialize(db_path, mode="live")
            for index, value in enumerate(([], None, "text", 42, False)):
                supervisor_id = f"bad-{index}"
                run_dir = project / ".factory" / "runs" / supervisor_id
                run_dir.mkdir(parents=True)
                (run_dir / "DELIVERY.json").write_text(json.dumps(value), encoding="utf-8")
                insert_run(db_path, project, run_id=f"run-{index}", supervisor_run_id=supervisor_id)
            queue = server.RunQueue(db_path, [{"id": "test", "name": "Test", "path": str(project)}], demo=False)
            queue._recover()
            self.assertEqual([server._run_row(db_path, f"run-{index}")["status"] for index in range(5)],
                             ["orphaned"] * 5)

    def test_reconciliation_skips_non_object_reports_and_continues(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            project = make_project(root / "project")
            runs_dir = project / ".factory" / "runs"
            for index, value in enumerate(([], None, "text", 42, False)):
                run_dir = runs_dir / f"bad-{index}"
                run_dir.mkdir(parents=True)
                (run_dir / "DELIVERY.json").write_text(json.dumps(value), encoding="utf-8")
            good_dir = runs_dir / "good"
            good_dir.mkdir(parents=True)
            (good_dir / "DELIVERY.json").write_text(
                json.dumps({"status": "verified_candidate", "request": "Valid legacy report"}), encoding="utf-8")
            db_path = root / "events.sqlite3"
            queue = server.RunQueue(db_path, [{"id": "test", "name": "Test", "path": str(project)}], demo=False)
            queue.start()
            queue.stop()
            db = connect(db_path)
            try:
                rows = db.execute("SELECT supervisor_run_id,status FROM runs ORDER BY supervisor_run_id").fetchall()
            finally:
                db.close()
            self.assertEqual([(row["supervisor_run_id"], row["status"]) for row in rows], [("good", "orphaned")])

    def test_report_only_verified_candidate_recovers_as_orphaned_not_ready(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            project = make_project(root / "project")
            run_dir = project / ".factory" / "runs" / "candidate"
            run_dir.mkdir(parents=True)
            (run_dir / "DELIVERY.json").write_text(json.dumps({"status": "verified_candidate"}), encoding="utf-8")
            db_path = root / "events.sqlite3"
            initialize(db_path, mode="live")
            insert_run(db_path, project, supervisor_run_id="candidate")
            queue = server.RunQueue(db_path, [{"id": "test", "name": "Test", "path": str(project)}], demo=False)
            queue._recover()
            run = server._run_row(db_path, "run-1")
            history = events_for(db_path, "run-1")
            self.assertEqual((run["status"], run["stage"]), ("orphaned", "Blocked"))
            self.assertNotIn("delivery_verified", [event["type"] for event in history])
            self.assertTrue((project / ".factory" / "active-run.json").is_file())

    def test_demo_start_never_imports_or_quarantines_real_checkout_reports(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            project = make_project(root / "project")
            report = project / ".factory" / "runs" / "old-run" / "DELIVERY.json"
            report.parent.mkdir(parents=True)
            report.write_text(json.dumps({"status": "verified_candidate"}), encoding="utf-8")
            db_path = root / "demo.sqlite3"
            queue = server.RunQueue(db_path, [{"id": "demo", "name": "Demo", "path": str(project)}], demo=True)
            queue.start()
            queue.stop()
            db = connect(db_path)
            try:
                self.assertEqual(db.execute("SELECT COUNT(*) FROM runs").fetchone()[0], 0)
            finally:
                db.close()
            self.assertFalse((project / ".factory" / "active-run.json").exists())


class DashboardApiTests(unittest.TestCase):
    async def wait_run(self, client: AsyncClient, run_id: str, token: str) -> dict:
        for _ in range(300):
            response = await client.get(f"/api/runs/{run_id}", headers={"X-CSRF-Token": token})
            self.assertEqual(response.status_code, 200, response.text)
            result = response.json()
            if result["status"] in ("completed", "blocked", "interrupted", "orphaned"):
                return result
            await asyncio.sleep(0.01)
        self.fail("demo run did not reach a terminal status")


    def test_live_ready_requires_persisted_event_and_matching_delivery_report(self):
        cases = (
            ("missing", None, True, False),
            ("mismatched", {"status": "blocked", "summary": "disk"}, True, False),
            ("report_only", {"status": "verified_candidate", "summary": "disk"}, False, False),
            ("verified", {"status": "verified_candidate", "summary": "disk"}, True, True),
        )
        for name, report, has_verified_event, ready in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                project = make_project(root / "project")
                supervisor_id = "candidate"
                if report is not None:
                    run_dir = project / ".factory" / "runs" / supervisor_id
                    run_dir.mkdir(parents=True)
                    (run_dir / "DELIVERY.json").write_text(json.dumps(report), encoding="utf-8")
                db_path = root / "events.sqlite3"
                initialize(db_path, mode="live")
                insert_run(db_path, project, supervisor_run_id=supervisor_id)
                with event_context(db_path, "run-1", "run-1"):
                    emit("run_started", {"supervisor_run_id": supervisor_id})
                    if has_verified_event:
                        emit("delivery_verified", {
                            "supervisor_run_id": supervisor_id,
                            "delivery_status": "verified_candidate",
                            "summary": "persisted event",
                        })
                projects_path = root / "projects.json"
                projects_path.write_text(json.dumps({"projects": [{
                    "id": "test", "name": "Test project", "path": str(project),
                }]}), encoding="utf-8")
                app = server.create_app(db_path=db_path, projects_path=projects_path)

                async def request_run(app=app, report=report, ready=ready):
                    async with AsyncClient(
                        transport=ASGITransport(app=app), base_url="http://127.0.0.1:8765"
                    ) as client:
                        token = (await client.get("/api/health")).json()["csrf_token"]
                        headers = {"X-CSRF-Token": token}
                        summary = (await client.get("/api/runs", headers=headers)).json()["runs"][0]
                        detail = (await client.get("/api/runs/run-1", headers=headers)).json()
                        if ready:
                            self.assertEqual(
                                (summary["status"], summary["stage"], summary["delivery_status"]),
                                ("completed", "Ready", "verified_candidate"),
                            )
                            self.assertEqual(summary["report"], report)
                        else:
                            self.assertFalse(
                                summary["status"] == "completed"
                                and summary["stage"] == "Ready"
                                and summary["delivery_status"] == "verified_candidate"
                            )
                        self.assertEqual(detail["report"], report)

                asyncio.run(request_run())

    def test_demo_http_flow_auth_replay_and_synthetic_detail_without_provider_processes(self):
        with tempfile.TemporaryDirectory() as temp:
            app = server.create_app(db_path=Path(temp) / "demo.sqlite3", demo=True, demo_delay=0)
            async def request_flow() -> None:
                app.state.queue.start()
                try:
                    with patch("app.server.subprocess.Popen", side_effect=AssertionError("demo must not launch providers")):
                        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://127.0.0.1:8765") as client:
                            self.assertEqual((await client.get("/api/runs")).status_code, 403)
                            health = await client.get("/api/health")
                            self.assertEqual(health.status_code, 200)
                            token = health.json()["csrf_token"]
                            origin = {"Origin": "http://127.0.0.1:8765", "X-CSRF-Token": token}
                            self.assertEqual((await client.post("/api/runs", json={"requirement": "test", "project_id": "demo"})).status_code, 403)
                            self.assertEqual((await client.post("/api/runs", headers={**origin, "Origin": "https://evil.invalid"},
                                                                json={"requirement": "test", "project_id": "demo", "demo_outcome": "ready"})).status_code, 403)
                            self.assertEqual((await client.post("/api/runs", headers=origin,
                                                                json={"requirement": "test", "project_id": "../../outside", "demo_outcome": "ready"})).status_code, 422)
                            ready_response = await client.post("/api/runs", headers=origin,
                                                               json={"requirement": "Synthetic run", "project_id": "demo", "demo_outcome": "ready"})
                            self.assertEqual(ready_response.status_code, 202, ready_response.text)
                            ready = await self.wait_run(client, ready_response.json()["run_id"], token)
                            self.assertEqual((ready["stage"], ready["delivery_status"]), ("Ready", "verified_candidate"))
                            self.assertEqual(ready["delivery"]["status"], "verified_candidate")
                            self.assertTrue(ready["delivery"]["synthetic"])
                            self.assertEqual(ready["delivery"]["summary"], "Demo fixture only; no code generated")
                            self.assertEqual(ready["delivery"]["round"], 2)
                            self.assertTrue(ready["delivery"]["gates"][0]["pass"])
                            self.assertTrue(ready["plan"]["synthetic"])
                            self.assertEqual(ready["plan"]["acceptance_criteria"][0]["id"], "DEMO-A1")
                            self.assertTrue(ready["design"][0]["synthetic"])
                            self.assertIn("demo_context", [event["type"] for event in ready["history"]])
                            self.assertTrue(any(event["type"] == "delivery_verified" and
                                                event["data"].get("delivery_status") == "verified_candidate"
                                                for event in ready["history"]))
                            self.assertEqual((await client.get(f"/api/runs/{ready['id']}")).status_code, 200)
                            blocked_response = await client.post("/api/runs", headers=origin,
                                                                 json={"requirement": "Blocked fixture", "project_id": "demo", "demo_outcome": "blocked"})
                            self.assertEqual(blocked_response.status_code, 202, blocked_response.text)
                            blocked = await self.wait_run(client, blocked_response.json()["run_id"], token)
                            self.assertEqual((blocked["stage"], blocked["status"]), ("Blocked", "blocked"))
                            self.assertEqual(blocked["delivery"]["status"], "blocked")
                            self.assertTrue(blocked["delivery"]["synthetic"])
                            self.assertEqual(blocked["delivery"]["summary"], "Demo fixture only; no code generated")
                            self.assertTrue(blocked["findings"])
                            self.assertIn("Repair", [event["data"].get("stage") for event in ready["history"] if event["type"] == "stage_entered"])
                            snapshot = (await client.get("/api/runs", headers={"X-CSRF-Token": token})).json()
                            self.assertGreater(snapshot["last_event_id"], 0)
                            replay = (await client.get(f"/api/runs/{ready['id']}/events?after=0",
                                                       headers={"X-CSRF-Token": token})).json()["events"]
                            self.assertEqual(replay[0]["type"], "run_created")
                            self.assertEqual((await client.get(f"/api/runs/{ready['id']}/artifacts?path=../../factory.config.json",
                                                               headers={"X-CSRF-Token": token})).status_code, 404)
                finally:
                    app.state.queue.stop()

            asyncio.run(request_flow())

    def test_concurrent_api_submissions_are_fifo(self):
        with tempfile.TemporaryDirectory() as temp:
            app = server.create_app(db_path=Path(temp) / "demo.sqlite3", demo=True, demo_delay=0)

            async def request_flow() -> None:
                with patch.object(server.RunQueue, "_loop", lambda _self: None):
                    app.state.queue.start()
                    try:
                        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://127.0.0.1:8765") as client:
                            token = (await client.get("/api/health")).json()["csrf_token"]
                            headers = {"Origin": "http://127.0.0.1:8765", "X-CSRF-Token": token}
                            responses = await asyncio.gather(*(client.post("/api/runs", headers=headers,
                                                                           json={"requirement": f"req-{index}", "project_id": "demo", "demo_outcome": "blocked"})
                                                              for index in range(12)))
                            self.assertTrue(all(response.status_code == 202 for response in responses))
                            queued = sorted(((response.json()["queue_position"], response.json()["run_id"])
                                             for response in responses))
                            self.assertEqual([position for position, _ in queued], list(range(1, 13)))
                            selected = [app.state.queue._next()["id"] for _ in range(12)]
                            self.assertEqual(selected, [run_id for _, run_id in queued])
                    finally:
                        app.state.queue.stop()

            asyncio.run(request_flow())

    def test_sse_replay_honors_last_event_id_over_after_parameter(self):
        with tempfile.TemporaryDirectory() as temp:
            db_path = Path(temp) / "demo.sqlite3"
            initialize(db_path, mode="demo")
            db = connect(db_path)
            try:
                for kind in ("first", "second", "third"):
                    add_event(db, "fixture", kind, {"status": "synthetic"})
            finally:
                db.close()
            app = server.create_app(db_path=db_path, demo=True, demo_delay=0)
            endpoint = next(route.endpoint for route in app.routes if getattr(route, "path", None) == "/api/events")

            async def replay_stream() -> None:
                scope = {"type": "http", "method": "GET", "path": "/api/events", "raw_path": b"/api/events",
                         "query_string": b"after=0", "scheme": "http", "server": ("127.0.0.1", 8765),
                         "headers": [(b"host", b"127.0.0.1:8765"), (b"x-csrf-token", app.state.csrf.encode()),
                                     (b"last-event-id", b"2")], "client": ("127.0.0.1", 1234),
                         "http_version": "1.1", "root_path": ""}
                async def receive():
                    return {"type": "http.request", "body": b"", "more_body": False}
                request = Request(scope, receive)
                calls = 0
                async def is_disconnected():
                    nonlocal calls
                    calls += 1
                    return calls > 1
                request.is_disconnected = is_disconnected
                response = endpoint(request, after=0)
                chunks = []
                async for chunk in response.body_iterator:
                    chunks.append(chunk.decode() if isinstance(chunk, bytes) else chunk)
                self.assertIn("id: 3\nevent: event", "".join(chunks))
                self.assertNotIn("id: 1\n", "".join(chunks))
                self.assertNotIn("id: 2\n", "".join(chunks))

            asyncio.run(replay_stream())

    def test_agent_timeout_event_sets_shared_unclean_flag_across_worker_context(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            project = make_project(root / "project")
            db_path = root / "events.sqlite3"
            initialize(db_path, mode="live")
            register_cli_run(db_path, "timeout-run", project, "Need", os.getpid(), process_birth(os.getpid()))
            safety = threading.Event()
            settings = {"providers": {"testing": "codex"}, "models": {"testing": "gpt-6-luna"}}
            with event_context(db_path, "timeout-run", "timeout-run"):
                token = factory.RUN_UNCLEAN.set(safety)
                try:
                    with checkout_lock(project):
                        claim = claim_checkout(project, "timeout-run", os.getpid(), process_birth(os.getpid()))
                        with patch("factory._execute_agent", side_effect=factory.AgentTimedOut("timeout")):
                            with ThreadPoolExecutor(max_workers=1) as pool:
                                copied = contextvars.copy_context()
                                future = pool.submit(copied.run, factory.execute_agent, "testing", "review", {}, settings,
                                                     project, root / "agent")
                                with self.assertRaises(factory.AgentTimedOut):
                                    future.result()
                        self.assertTrue(safety.is_set())
                        if not safety.is_set():
                            claim.release_after_worker_exit()
                        self.assertTrue((project / ".factory" / "active-run.json").is_file())
                        with self.assertRaises(CheckoutQuarantined):
                            claim_checkout(project, "second-run", os.getpid(), process_birth(os.getpid()))
                        kinds = [event["type"] for event in events_for(db_path, "timeout-run")]
                        self.assertEqual(kinds[-2:], ["agent_started", "agent_timed_out"])
                finally:
                    factory.RUN_UNCLEAN.reset(token)

    def test_elapsed_time_freezes_at_dry_run_completion(self):
        events = [
            {"type": "run_started", "timestamp": "2026-10-21T00:00:00+00:00", "data": {}},
            {"type": "run_completed", "timestamp": "2026-10-21T00:00:08+00:00", "data": {"delivery_status": "dry_run"}},
        ]
        self.assertEqual(server._elapsed(events, events[0]["timestamp"]), 8)


if __name__ == "__main__":
    unittest.main()
