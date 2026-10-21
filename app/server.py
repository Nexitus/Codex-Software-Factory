from __future__ import annotations

import asyncio
import hmac
import json
import os
import re
import secrets
import sqlite3
import subprocess
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from .checkout_lock import CheckoutBusy
from .events import (
    add_event,
    connect,
    emit,
    event_context,
    events_for,
    initialize,
    redact,
    utc_now,
)
from .process_guard import process_birth, process_matches
from .projector import project_run

UTC = timezone(timedelta(0), name="UTC")

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_FILES = {"manifest.json", "dry-run.json", "DELIVERY.json", "ERROR.json", "plan/parsed.json", "design/*/parsed.json", "build-dispatch/parsed.json",
                  "build-initial/parsed.json", "review-round-*/gates.json", "review-round-*/reviews.json",
                  "review-round-*/blockers.json", "review-round-*/reviews/*/parsed.json", "repair-plan-*/parsed.json",
                  "repair-*/parsed.json"}
ARTIFACT_RE = re.compile(r"^(?:manifest\.json|dry-run\.json|DELIVERY\.json|ERROR\.json|(?:plan|build-dispatch|build-initial|repair-plan-[^/]+|repair-[^/]+)/parsed\.json|design/[^/]+/parsed\.json|review-round-[^/]+/(?:gates\.json|reviews\.json|blockers\.json|reviews/[^/]+/parsed\.json))$")


def _project_root(path: str | Path) -> Path:
    candidate = Path(path).expanduser().resolve(strict=True)
    if not candidate.is_dir():
        raise ValueError("Configured project path must be a directory")
    return candidate


def _marker_path(project_path: str | Path) -> Path:
    root = Path(project_path).resolve(strict=True)
    candidate = root / ".factory"
    candidate.mkdir(parents=True, exist_ok=True)
    directory = candidate.resolve(strict=True)
    if not directory.is_relative_to(root):
        raise ValueError("Project .factory path resolves outside its allowlisted checkout")
    return directory / "active-run.json"


def _public_run(run: dict[str, Any], *, include_history: bool) -> dict[str, Any]:
    keys = {"id", "project_id", "project_name", "requirement", "status", "stage", "created_at", "updated_at",
            "queue_position", "supervisor_run_id", "round", "max_rounds", "agents", "gates", "findings",
            "active_findings", "finding_counts", "delivery_status", "delivery", "blockers", "error_summary",
            "elapsed_seconds", "report", "artifacts", "plan", "design", "log_refs", "events", "history"}
    if not include_history:
        keys.discard("events")
        keys.discard("history")
    return {key: run[key] for key in keys if key in run}


def load_projects(path: Path | None = None) -> list[dict[str, str]]:
    config_path = path or ROOT / "dashboard.projects.json"
    if not config_path.exists():
        raise ValueError("Live dashboard requires dashboard.projects.json with an explicit project allowlist")
    data = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("projects"), list) or not data["projects"]:
        raise ValueError("dashboard.projects.json must contain a nonempty projects list")
    projects = []
    ids, roots = set(), set()
    for raw in data["projects"]:
        if not isinstance(raw, dict) or set(raw) != {"id", "name", "path"}:
            raise ValueError("Each project must contain exactly id, name, and path")
        if not all(isinstance(raw[key], str) and raw[key].strip() for key in ("id", "name", "path")):
            raise ValueError("Project id, name, and path must be nonempty strings")
        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}", raw["id"]):
            raise ValueError("Project IDs may contain only letters, numbers, underscores, and dashes")
        project_path = Path(raw["path"]).expanduser()
        if not project_path.is_absolute():
            project_path = config_path.parent / project_path
        root = _project_root(project_path)
        if len(raw["name"]) > 100 or raw["id"] in ids or str(root).casefold() in roots:
            raise ValueError("Project names must be at most 100 characters; IDs and canonical roots must be unique")
        ids.add(raw["id"])
        roots.add(str(root).casefold())
        projects.append({"id": raw["id"], "name": raw["name"], "path": str(root)})
    return projects


def _allowed_host(request: Request, port: int) -> bool:
    try:
        host = request.headers.get("host", "")
        parsed = urlsplit("//" + host)
        return parsed.hostname in {"localhost", "127.0.0.1", "::1"} and parsed.port in (None, port)
    except ValueError:
        return False


def _same_origin(request: Request) -> bool:
    origin = request.headers.get("origin")
    if not origin:
        return False
    try:
        parsed = urlsplit(origin)
        return (parsed.scheme == request.url.scheme and parsed.hostname == request.url.hostname
                and (parsed.port or (443 if parsed.scheme == "https" else 80)) == (request.url.port or 80))
    except ValueError:
        return False


def _read_auth(request: Request, csrf: str) -> None:
    candidate = request.headers.get("x-csrf-token") or request.cookies.get("factory_csrf") or ""
    if not candidate or not hmac.compare_digest(candidate, csrf):
        raise HTTPException(403, "Read authorization required")


def _run_row(path: Path, run_id: str) -> dict[str, Any] | None:
    db = connect(path)
    try:
        row = db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
        return dict(row) if row else None
    finally:
        db.close()


def _elapsed(events: list[dict[str, Any]], fallback_created: str) -> int:
    started = next((e["timestamp"] for e in events if e["type"] == "run_started"), None)
    if not started:
        return 0
    ended = next((e["timestamp"] for e in reversed(events) if e["type"] in
                  ("delivery_verified", "run_blocked", "run_interrupted", "run_orphaned", "run_completed")), None)
    start = datetime.fromisoformat(started)
    end = datetime.fromisoformat(ended) if ended else datetime.now(UTC)
    return max(0, int((end - start).total_seconds()))


def _all_events(path: Path, run_id: str, cursor: int | None = None) -> list[dict[str, Any]]:
    db = connect(path)
    try:
        query = "SELECT seq,run_id,type,timestamp,data_json FROM events WHERE run_id=?"
        args: tuple[Any, ...] = (run_id,)
        if cursor is not None:
            query += " AND seq<=?"
            args += (cursor,)
        rows = db.execute(query + " ORDER BY seq", args).fetchall()
        return [{"id": row["seq"], "seq": row["seq"], "run_id": row["run_id"], "type": row["type"],
                 "timestamp": row["timestamp"], "data": json.loads(row["data_json"])} for row in rows]
    finally:
        db.close()


class RunQueue:
    def __init__(self, db_path: Path, projects: list[dict[str, str]], demo: bool, demo_delay: float = 0.25):
        self.db_path, self.projects, self.demo, self.demo_delay = db_path, projects, demo, demo_delay
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._loop, name="factory-run-queue", daemon=True)

    def start(self) -> None:
        initialize(self.db_path, mode="demo" if self.demo else "live")
        if not self.demo:
            self._reconcile_reports()
            self._recover()
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        if self.thread.is_alive():
            self.thread.join(timeout=5)

    def _recover(self) -> None:
        db = connect(self.db_path)
        try:
            rows = db.execute("SELECT * FROM runs WHERE status IN ('running','starting')").fetchall()
            for row in rows:
                if process_matches(row["worker_pid"], row["worker_token"]):
                    continue
                report = self._existing_report(dict(row))
                marker = _marker_path(project["path"]) if (project := next((p for p in self.projects if p["id"] == row["project_id"]), None)) else None
                if report is not None and marker is not None and not marker.exists():
                    run_id = row["id"]
                    with event_context(self.db_path, run_id, run_id):
                        emit("run_blocked", {"supervisor_run_id": row["supervisor_run_id"], "blockers": report.get("blockers", []),
                                             "error_summary": report.get("error"), "attempt": "recovery"})
                        emit("run_completed", {"delivery_status": "blocked", "attempt": "recovery"})
                    continue
                if marker is not None and not marker.exists():
                    self._write_orphan_marker(Path(project["path"]), row["id"], row["worker_pid"], row["worker_token"])
                db.execute("BEGIN IMMEDIATE")
                add_event(db, row["id"], "run_orphaned", {"status": "orphaned", "stage": "Blocked", "round": None,
                                                               "attempt": "recovery", "reason": "recovery_required"})
                db.execute("UPDATE runs SET status='orphaned',stage='Blocked',updated_at=? WHERE id=?", (utc_now(), row["id"]))
                db.commit()
        finally:
            db.close()

    def _existing_report(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not row.get("supervisor_run_id"):
            return None
        project = next((p for p in self.projects if p["id"] == row["project_id"]), None)
        if not project:
            return None
        supervisor_id = row["supervisor_run_id"]
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", supervisor_id):
            return None
        root = Path(project["path"]).resolve()
        runs_root = (root / ".factory" / "runs").resolve()
        run_dir = (runs_root / supervisor_id).resolve()
        if not runs_root.is_relative_to(root) or not run_dir.is_relative_to(runs_root):
            return None
        path = run_dir / "DELIVERY.json"
        try:
            if not path.resolve(strict=True).is_relative_to(run_dir):
                return None
            report = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(report, dict):
                return None
            # Report-only recovery may restore a blocked state. Ready requires the
            # persisted supervisor delivery_verified event, never a report claim alone.
            return report if report.get("status") == "blocked" else None
        except (OSError, ValueError):
            return None

    def _write_orphan_marker(self, project: Path, run_id: str, pid: int | None, token: str | None) -> None:
        marker = _marker_path(project)
        if marker.is_symlink():
            return
        try:
            marker.parent.mkdir(parents=True, exist_ok=True)
            with marker.open("x", encoding="utf-8") as stream:
                json.dump({"run_id": run_id, "pid": pid, "process_birth": token,
                           "status": "orphaned", "reason": "recovery_required", "created_at": utc_now()}, stream)
        except (FileExistsError, OSError):
            pass

    def _reconcile_reports(self) -> None:
        """Import legacy supervisor reports absent from the durable event database."""
        db = connect(self.db_path)
        try:
            for project in self.projects:
                root = Path(project["path"]).resolve(strict=True)
                marker_path = _marker_path(root)
                runs_dir = marker_path.parent / "runs"
                if not runs_dir.is_dir():
                    continue
                resolved_runs = runs_dir.resolve(strict=True)
                if not resolved_runs.is_relative_to(root):
                    continue
                for report_path in sorted(runs_dir.glob("*/DELIVERY.json")):
                    try:
                        if not report_path.resolve(strict=True).is_relative_to(resolved_runs):
                            continue
                    except (OSError, ValueError):
                        continue
                    supervisor_id = report_path.parent.name
                    if db.execute("SELECT 1 FROM runs WHERE project_path=? AND supervisor_run_id=? LIMIT 1",
                                  (project["path"], supervisor_id)).fetchone():
                        continue
                    try:
                        report = json.loads(report_path.read_text(encoding="utf-8"))
                        if not isinstance(report, dict) or report.get("status") not in ("verified_candidate", "blocked"):
                            continue
                    except (OSError, ValueError):
                        continue
                    run_id = "legacy-" + uuid.uuid5(uuid.NAMESPACE_URL, f"{project['path']}:{supervisor_id}").hex[:24]
                    now = datetime.fromtimestamp(report_path.stat().st_mtime, UTC).isoformat()
                    req = redact(str(report.get("request", "Legacy supervisor report") or "Legacy supervisor report"))[:20000]
                    status = "blocked" if report.get("status") == "blocked" else "orphaned"
                    stage = "Blocked"
                    reason = "legacy_report_requires_review" if status == "orphaned" else None
                    db.execute("BEGIN IMMEDIATE")
                    db.execute("INSERT OR IGNORE INTO runs(id,project_id,project_name,project_path,requirement,status,stage,created_at,updated_at,queue_position,supervisor_run_id,report_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                               (run_id, project["id"], project["name"], project["path"], req, status, stage, now, now, 0, supervisor_id, None))
                    add_event(db, run_id, "run_created", {"status": "queued", "stage": "Queue", "attempt": "legacy-reconcile"})
                    add_event(db, run_id, "run_queued", {"status": "queued", "stage": "Queue", "attempt": "legacy-reconcile"})
                    add_event(db, run_id, "run_started", {"status": "running", "stage": "Planning", "supervisor_run_id": supervisor_id, "attempt": "legacy-reconcile"})
                    if status == "blocked":
                        add_event(db, run_id, "run_blocked", {"status": "blocked", "stage": "Blocked", "blockers": redact(report.get("blockers", [])), "attempt": "legacy-reconcile"})
                        add_event(db, run_id, "run_completed", {"status": "blocked", "delivery_status": "blocked", "attempt": "legacy-reconcile"})
                    else:
                        add_event(db, run_id, "run_orphaned", {"status": "orphaned", "stage": "Blocked", "reason": reason, "attempt": "legacy-reconcile"})
                    db.commit()
                    if status == "orphaned":
                        self._write_orphan_marker(Path(project["path"]), run_id, None, None)
        finally:
            db.close()

    def _next(self) -> dict[str, Any] | None:
        db = connect(self.db_path)
        try:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM runs WHERE status='queued' ORDER BY queue_position,created_at LIMIT 1").fetchone()
            if row is None:
                db.commit()
                return None
            changed = db.execute("UPDATE runs SET status='starting',updated_at=? WHERE id=? AND status='queued'",
                                 (utc_now(), row["id"])).rowcount
            db.commit()
            return dict(row) if changed else None
        finally:
            db.close()

    def _loop(self) -> None:
        while not self.stop_event.is_set():
            self._recover()
            if self._active_workers():
                self.stop_event.wait(0.25)
                continue
            row = self._next()
            if row is None:
                self.stop_event.wait(0.25)
                continue
            try:
                self._execute(row)
            except CheckoutBusy:
                db = connect(self.db_path)
                try:
                    db.execute("UPDATE runs SET status='queued',updated_at=? WHERE id=? AND status='starting'", (utc_now(), row["id"]))
                finally:
                    db.close()
                self.stop_event.wait(0.5)
            except (OSError, ValueError, RuntimeError, sqlite3.Error) as exc:
                with event_context(self.db_path, row["id"], row["id"]):
                    emit("run_blocked", {"reason": type(exc).__name__, "stage": "Blocked", "attempt": "run"})
                    emit("run_completed", {"delivery_status": "blocked", "attempt": "run"})

    def _execute(self, row: dict[str, Any]) -> None:
        project = next((item for item in self.projects if item["id"] == row["project_id"]), None)
        if project is None:
            raise ValueError("Project is no longer allowlisted")
        root = Path(project["path"])
        if self.demo:
            with event_context(self.db_path, row["id"], row["id"]):
                self._demo_run(row)
            return
        config_path = (root / "factory.config.json").resolve(strict=True)
        if not config_path.is_relative_to(root.resolve()):
            raise ValueError("Project config must stay inside its allowlisted checkout")
        command = [os.fspath(Path(os.sys.executable)), os.fspath(ROOT / "factory.py"), "--idea", row["requirement"],
                   "--project", str(root), "--config", str(config_path), "--event-db", str(self.db_path),
                   "--run-id", row["id"], "--queue-token", row["handoff_token"], "--wait-for-lock"]
        process = subprocess.Popen(command, cwd=ROOT, stdin=subprocess.DEVNULL,
                                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                                 start_new_session=(os.name != "nt"),
                                                 creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
        db = connect(self.db_path)
        try:
            # The CLI may already have registered its own PID before this parent
            # resumes; never overwrite that authoritative child identity.
            db.execute("UPDATE runs SET worker_pid=?,worker_token=?,updated_at=? WHERE id=? AND status='starting' AND worker_pid IS NULL",
                       (process.pid, process_birth(process.pid), utc_now(), row["id"]))
        finally:
            db.close()
        process.wait()
        current = _run_row(self.db_path, row["id"])
        if current and current["status"] in ("starting", "running"):
            self._recover()

    def _active_workers(self) -> bool:
        db = connect(self.db_path)
        try:
            rows = db.execute("SELECT worker_pid,worker_token FROM runs WHERE status IN ('starting','running')").fetchall()
        finally:
            db.close()
        active = False
        for row in rows:
            if process_matches(row["worker_pid"], row["worker_token"]):
                active = True
        return active

    def _demo_emit(self, run_id: str, kind: str, data: dict[str, Any]) -> None:
        if self.stop_event.is_set():
            raise RuntimeError("demo_interrupted")
        emit(kind, data)
        self.stop_event.wait(self.demo_delay)

    def _demo_run(self, row: dict[str, Any]) -> None:
        rid, outcome = row["id"], row["demo_outcome"]
        self._demo_emit(rid, "run_started", {"supervisor_run_id": "demo-" + rid[:8], "max_rounds": 2, "attempt": "run"})
        self._demo_emit(rid, "demo_context", {
            "synthetic": True,
            "plan": {
                "synthetic": True,
                "summary": "Synthetic demo plan: implement a small example and verify its behavior.",
                "acceptance_criteria": [{"id": "DEMO-A1", "description": "The example behavior is represented clearly.",
                                         "verification": "Synthetic unit-test gate passes after repair."}],
                "work_items": [{"id": "DEMO-W1", "description": "Review and repair the example implementation.",
                                "verification": "Synthetic independent review passes in round 2."}],
                "assumptions": ["This fixture does not create or modify application files."],
                "risks": ["Synthetic evidence does not verify a real repository change."],
            },
            "design": [{"role": "architecture", "synthetic": True,
                        "guidance": ["Keep the example behavior small and explicit."],
                        "checks": ["Inspect the example flow after the simulated repair."],
                        "risks": ["Fixture-only design guidance."], "blocking_questions": []}],
        })
        for stage, role, phase in (("Planning", "planner", "plan"), ("Design", "testing", "design"), ("Build", "builder", "build")):
            self._demo_emit(rid, "stage_entered", {"stage": stage, "attempt": phase})
            self._demo_emit(rid, "agent_started", {"role": role, "phase": phase, "provider": "demo", "model": "none", "attempt": phase})
            self._demo_emit(rid, "agent_succeeded", {"role": role, "phase": phase, "provider": "demo", "model": "none", "seconds": self.demo_delay, "attempt": phase})
            self._demo_emit(rid, "stage_completed", {"stage": stage, "attempt": phase})
        self._demo_emit(rid, "round_incremented", {"round": 1, "max_rounds": 2, "attempt": "review"})
        self._demo_emit(rid, "stage_entered", {"stage": "Review", "attempt": "review"})
        self._demo_emit(rid, "gate_started", {"name": "unit-tests", "round": 1, "attempt": "gate"})
        self._demo_emit(rid, "gate_passed", {"name": "unit-tests", "round": 1, "exit_code": 0, "attempt": "gate"})
        self._demo_emit(rid, "agent_started", {"role": "architecture", "phase": "review", "provider": "demo", "model": "none", "attempt": "review"})
        self._demo_emit(rid, "agent_succeeded", {"role": "architecture", "phase": "review", "provider": "demo", "model": "none", "verdict": "fail", "attempt": "review"})
        finding = {"id": "DEMO-1", "severity": "medium", "file": "example.py", "evidence": "The first review found a demonstration issue.", "remediation": "Apply the simulated repair.", "role": "architecture", "round": 1, "attempt": "review"}
        self._demo_emit(rid, "finding_recorded", finding)
        if outcome == "blocked":
            self._demo_emit(rid, "run_blocked", {"blockers": ["review:architecture:fail"], "attempt": "review"})
            self._demo_emit(rid, "run_completed", {"delivery_status": "blocked", "attempt": "run"})
            return
        self._demo_emit(rid, "repair_requested", {"round": 1, "blocker_count": 1, "attempt": "repair"})
        self._demo_emit(rid, "stage_entered", {"stage": "Repair", "attempt": "repair"})
        self._demo_emit(rid, "repair_started", {"round": 1, "attempt": "repair"})
        self._demo_emit(rid, "agent_started", {"role": "builder", "phase": "repair", "provider": "demo", "model": "none", "attempt": "repair"})
        self._demo_emit(rid, "agent_succeeded", {"role": "builder", "phase": "repair", "provider": "demo", "model": "none", "attempt": "repair"})
        self._demo_emit(rid, "stage_completed", {"stage": "Repair", "attempt": "repair"})
        self._demo_emit(rid, "round_incremented", {"round": 2, "max_rounds": 2, "attempt": "review"})
        self._demo_emit(rid, "stage_entered", {"stage": "Review", "attempt": "review"})
        self._demo_emit(rid, "gate_started", {"name": "unit-tests", "round": 2, "attempt": "gate"})
        self._demo_emit(rid, "gate_passed", {"name": "unit-tests", "round": 2, "exit_code": 0, "attempt": "gate"})
        self._demo_emit(rid, "agent_started", {"role": "architecture", "phase": "review", "provider": "demo", "model": "none", "attempt": "review"})
        self._demo_emit(rid, "agent_succeeded", {"role": "architecture", "phase": "review", "provider": "demo", "model": "none", "verdict": "pass", "attempt": "review"})
        self._demo_emit(rid, "delivery_verified", {"supervisor_run_id": "demo-" + rid[:8], "round": 2,
                                                       "delivery_status": "verified_candidate", "synthetic": True,
                                                       "gates": [{"name": "unit-tests", "pass": True}], "attempt": "review"})
        self._demo_emit(rid, "run_completed", {"delivery_status": "verified_candidate", "attempt": "run"})


def create_app(*, db_path: Path | None = None, projects_path: Path | None = None, demo: bool = False,
               port: int = 8765, demo_delay: float = 0.25) -> FastAPI:
    database = (db_path or ROOT / ".factory" / ("dashboard-demo.sqlite3" if demo else "dashboard.sqlite3")).resolve()
    projects = ([{"id": "demo", "name": "Factory Demo", "path": str(ROOT)}] if demo else load_projects(projects_path))
    initialize(database, mode="demo" if demo else "live")
    csrf = secrets.token_urlsafe(32)
    queue = RunQueue(database, projects, demo, demo_delay)
    app = FastAPI(title="Software Factory Dashboard")
    app.state.db_path, app.state.projects, app.state.demo, app.state.csrf = database, projects, demo, csrf
    app.state.queue = queue
    def _demo_delivery_report(run_events: list[dict[str, Any]], projected: dict[str, Any]) -> dict[str, Any] | None:
        verified_event = next((event for event in reversed(run_events)
                               if event["type"] == "delivery_verified" and
                               event["data"].get("delivery_status") == "verified_candidate"), None)
        if verified_event:
            data = verified_event["data"]
            return {
                "status": "verified_candidate", "synthetic": True,
                "summary": "Demo fixture only; no code generated",
                "round": data.get("round"), "review_rounds": data.get("review_rounds"),
                "gates": data.get("gates", []),
            }
        blocked_event = next((event for event in reversed(run_events)
                              if event["type"] == "run_blocked" and
                              projected.get("delivery_status") == "blocked"), None)
        if blocked_event:
            return {
                "status": "blocked", "synthetic": True,
                "summary": "Demo fixture only; no code generated",
                "round": projected.get("round"), "blockers": blocked_event["data"].get("blockers", []),
                "gates": projected.get("gates", []),
            }
        return None


    @app.on_event("startup")
    def _startup() -> None:
        queue.start()

    @app.on_event("shutdown")
    def _shutdown() -> None:
        queue.stop()

    @app.middleware("http")
    async def secure_local_requests(request: Request, call_next):
        if not _allowed_host(request, port):
            return JSONResponse({"detail": "Host must be a loopback address"}, status_code=400)
        origin = request.headers.get("origin")
        if origin and not _same_origin(request):
            return JSONResponse({"detail": "Cross-origin requests are not allowed"}, status_code=403)
        return await call_next(request)

    @app.get("/api/health")
    def health(request: Request):
        response = JSONResponse({"mode": "demo" if demo else "live", "csrf_token": csrf,
                                 "projects": [{"id": item["id"], "name": item["name"]} for item in projects]})
        response.set_cookie("factory_csrf", csrf, httponly=True, samesite="strict", secure=False, path="/api")
        return response

    @app.get("/api/runs")
    def list_runs(request: Request):
        _read_auth(request, csrf)
        db = connect(database)
        try:
            db.execute("BEGIN")
            cursor = int(db.execute("SELECT COALESCE(MAX(seq),0) FROM events").fetchone()[0])
            rows = db.execute("SELECT * FROM runs ORDER BY created_at DESC LIMIT 200").fetchall()
            queue = db.execute("SELECT id FROM runs WHERE status='queued' ORDER BY queue_position,created_at").fetchall()
            queue_positions = {item["id"]: index for index, item in enumerate(queue, 1)}
            allowed_paths = {str(Path(item["path"]).resolve()).casefold(): item for item in projects}
            result = []
            for raw in rows:
                row = dict(raw)
                configured = allowed_paths.get(str(Path(row["project_path"]).resolve()).casefold())
                if configured is None:
                    continue
                row["project_id"], row["project_name"] = configured["id"], configured["name"]
                events = _all_events(database, row["id"], cursor)
                projected = project_run(row, events)
                projected["elapsed_seconds"] = _elapsed(events, row["created_at"])
                projected["project_path"] = None
                projected["requirement"] = row["requirement"]
                projected["project_name"] = row["project_name"]
                projected["project_id"] = row["project_id"]
                projected["supervisor_run_id"] = row["supervisor_run_id"]
                projected["created_at"], projected["updated_at"] = row["created_at"], row["updated_at"]
                projected["queue_position"] = queue_positions.get(row["id"])
                projected["report"] = json.loads(row["report_json"]) if row["report_json"] else None
                if demo:
                    report = _demo_delivery_report(events, projected)
                    if report is not None:
                        projected["report"] = report
                        projected["delivery"] = report
                elif projected.get("delivery_status") == "verified_candidate":
                    verified_event = any(
                        event["type"] == "delivery_verified"
                        and event["data"].get("delivery_status") == "verified_candidate"
                        for event in events
                    )
                    report = (_artifact_json(configured, row["supervisor_run_id"], "DELIVERY.json")
                              if row["supervisor_run_id"] else None)
                    if verified_event and isinstance(report, dict) and report.get("status") == "verified_candidate":
                        projected["report"] = report
                        projected["delivery"] = report
                    else:
                        projected["delivery_status"] = "pending"
                        projected["report"] = report
                        projected["delivery"] = report
                result.append(_public_run(projected, include_history=False))
        finally:
            db.rollback()
            db.close()
        return {"runs": result, "active_run_id": next((item["id"] for item in result if item["status"] in ("starting", "running")), None),
                "queued_run_ids": [item["id"] for item in result if item["status"] == "queued"], "last_event_id": cursor}

    @app.get("/api/runs/{run_id}")
    def get_run(run_id: str, request: Request):
        _read_auth(request, csrf)
        row = _run_row(database, run_id)
        if row is None:
            raise HTTPException(404, "Run not found")
        projected = project_run(row, _all_events(database, run_id))
        project = next((item for item in projects if item["id"] == row["project_id"]), None)
        projected["project_name"] = row["project_name"]
        projected["project_id"] = row["project_id"]
        projected["requirement"] = row["requirement"]
        projected["created_at"], projected["updated_at"] = row["created_at"], row["updated_at"]
        run_events = projected["history"]
        projected["elapsed_seconds"] = _elapsed(run_events, row["created_at"])
        projected["supervisor_run_id"] = row["supervisor_run_id"]
        projected["events"] = run_events
        projected["history"] = run_events
        projected.pop("project_path", None)
        projected.pop("report_json", None)
        projected["report"] = (_artifact_json(project, row["supervisor_run_id"], "DELIVERY.json") or
                                _artifact_json(project, row["supervisor_run_id"], "ERROR.json")) if project and row["supervisor_run_id"] else None
        projected["artifacts"] = _artifacts(project, row["supervisor_run_id"]) if project and row["supervisor_run_id"] else []
        if demo:
            projected["plan"] = projected.get("demo_plan")
            projected["design"] = projected.get("demo_design", [])
            demo_report = _demo_delivery_report(run_events, projected)
            if demo_report is not None:
                projected["report"] = demo_report
        else:
            projected["plan"] = _artifact_json(project, row["supervisor_run_id"], "plan/parsed.json") if project and row["supervisor_run_id"] else None
            projected["design"] = _design_summaries(project, row["supervisor_run_id"]) if project and row["supervisor_run_id"] else []
        projected["delivery"] = projected["report"] or projected.get("delivery")
        projected["log_refs"] = _log_refs(project, row["supervisor_run_id"]) if project and row["supervisor_run_id"] else []
        return _public_run(projected, include_history=True)

    @app.get("/api/runs/{run_id}/events")
    def get_run_events(run_id: str, request: Request, after: int = 0):
        _read_auth(request, csrf)
        if _run_row(database, run_id) is None:
            raise HTTPException(404, "Run not found")
        return {"events": events_for(database, run_id, max(0, after), 5000)}

    @app.get("/api/runs/{run_id}/artifacts")
    def get_run_artifacts(run_id: str, request: Request, path: str | None = None):
        _read_auth(request, csrf)
        row = _run_row(database, run_id)
        if row is None:
            raise HTTPException(404, "Run not found")
        project = next((item for item in projects if item["id"] == row["project_id"]), None)
        if not project or not row["supervisor_run_id"]:
            if path is None:
                return {"artifacts": []}
            raise HTTPException(404, "Artifact not found")
        artifacts = _artifacts(project, row["supervisor_run_id"])
        if path is None:
            return {"artifacts": artifacts}
        content = _artifact_json(project, row["supervisor_run_id"], path)
        if content is None:
            raise HTTPException(404, "Artifact not found")
        return {"path": path, "content": content}

    @app.post("/api/runs", status_code=202)
    async def create_run(request: Request):
        if not _same_origin(request):
            raise HTTPException(403, "Same-origin submission required")
        token = request.headers.get("x-csrf-token", "")
        if not token or not hmac.compare_digest(token, csrf):
            raise HTTPException(403, "CSRF token required")
        try:
            body = await request.json()
        except ValueError as exc:
            raise HTTPException(400, "Expected JSON") from exc
        if not isinstance(body, dict) or set(body) - {"requirement", "project_id", "demo_outcome"}:
            raise HTTPException(400, "Invalid run request")
        requirement, project_id = body.get("requirement"), body.get("project_id")
        if not isinstance(requirement, str) or not requirement.strip() or len(requirement) > 20000:
            raise HTTPException(422, "Requirement must contain 1 to 20,000 characters")
        project = next((item for item in projects if item["id"] == project_id), None)
        if project is None:
            raise HTTPException(422, "Project is not allowlisted")
        outcome = body.get("demo_outcome")
        if demo:
            if outcome not in ("ready", "blocked"):
                raise HTTPException(422, "demo_outcome must be ready or blocked")
        elif outcome is not None:
            raise HTTPException(422, "demo_outcome is available only in demo mode")
        req = redact(requirement.strip())
        run_id, now = str(uuid.uuid4()), utc_now()
        db = connect(database)
        try:
            db.execute("BEGIN IMMEDIATE")
            position = int(db.execute("SELECT COALESCE(MAX(queue_position),0)+1 FROM runs WHERE status='queued'").fetchone()[0])
            handoff_token = secrets.token_urlsafe(32) if not demo else None
            db.execute("INSERT INTO runs(id,project_id,project_name,project_path,requirement,status,stage,created_at,updated_at,queue_position,demo_outcome,handoff_token) VALUES(?,?,?,?,?,'queued','Queue',?,?,?,?,?)",
                       (run_id, project["id"], project["name"], project["path"], req, now, now, position, outcome, handoff_token))
            data = {"project_id": project["id"], "project_name": project["name"], "status": "queued", "stage": "Queue",
                    "round": None, "attempt": "run"}
            add_event(db, run_id, "run_created", data)
            add_event(db, run_id, "run_queued", data)
            db.commit()
        except sqlite3.IntegrityError as exc:
            db.rollback()
            raise HTTPException(409, "Run could not be queued") from exc
        finally:
            db.close()
        return {"run_id": run_id, "status": "queued", "queue_position": position}

    @app.get("/api/projects")
    def get_projects(request: Request):
        _read_auth(request, csrf)
        return {"projects": [{"id": item["id"], "name": item["name"]} for item in projects]}

    @app.get("/api/events")
    def stream_events(request: Request, after: int = 0):
        _read_auth(request, csrf)
        header = request.headers.get("last-event-id")
        try:
            cursor = max(0, int(header)) if header else max(0, after)
        except ValueError as exc:
            raise HTTPException(400, "Last-Event-ID must be an integer") from exc

        async def stream():
            nonlocal cursor
            while not await request.is_disconnected():
                db = connect(database)
                try:
                    rows = db.execute("SELECT seq,run_id,type,timestamp,data_json FROM events WHERE seq>? ORDER BY seq LIMIT 250", (cursor,)).fetchall()
                finally:
                    db.close()
                if rows:
                    for row in rows:
                        cursor = int(row["seq"])
                        event = {"id": cursor, "seq": cursor, "run_id": row["run_id"], "type": row["type"],
                                 "timestamp": row["timestamp"], "data": json.loads(row["data_json"])}
                        yield f"id: {cursor}\nevent: event\ndata: {json.dumps(event, ensure_ascii=False, separators=(',', ':'))}\n\n"
                else:
                    yield ": keep-alive\n\n"
                    await asyncio.sleep(0.5)
        return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    dist = ROOT / "dashboard" / "dist"
    if dist.is_dir():
        from fastapi.staticfiles import StaticFiles
        app.mount("/", StaticFiles(directory=dist, html=True), name="dashboard")
    return app


def _artifacts(project: dict[str, str], supervisor_id: str) -> list[dict[str, Any]]:
    root = Path(project["path"]).resolve()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", supervisor_id) or supervisor_id in (".", ".."):
        return []
    runs_root = (root / ".factory" / "runs").resolve()
    run_dir = (runs_root / supervisor_id).resolve()
    if not runs_root.is_relative_to(root) or not run_dir.is_relative_to(runs_root) or not run_dir.is_dir():
        return []
    candidates = []
    for pattern in ARTIFACT_FILES:
        candidates.extend(run_dir.glob(pattern))
    result = []
    for file in sorted(set(candidates)):
        try:
            resolved = file.resolve(strict=True)
            if not resolved.is_relative_to(run_dir) or not resolved.is_file():
                continue
            rel = file.relative_to(run_dir).as_posix()
            if not ARTIFACT_RE.fullmatch(rel):
                continue
            result.append({"path": rel, "name": file.name, "kind": file.suffix.lstrip("."), "size": min(resolved.stat().st_size, 10_000_000)})
        except (OSError, ValueError):
            continue
    return result


def _artifact_json(project: dict[str, str], supervisor_id: str, relative: str) -> Any | None:
    if not ARTIFACT_RE.fullmatch(relative):
        return None
    root = Path(project["path"]).resolve()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", supervisor_id) or supervisor_id in (".", ".."):
        return None
    runs_root = (root / ".factory" / "runs").resolve()
    run_dir = (runs_root / supervisor_id).resolve()
    if not runs_root.is_relative_to(root) or not run_dir.is_relative_to(runs_root):
        return None
    file = run_dir / relative
    try:
        resolved = file.resolve(strict=True)
        if not resolved.is_relative_to(run_dir) or not resolved.is_file() or resolved.stat().st_size > 10_000_000:
            return None
        value = json.loads(resolved.read_text(encoding="utf-8"))
        if relative == "DELIVERY.json" and not isinstance(value, dict):
            return None
        return redact(value)
    except (OSError, ValueError, json.JSONDecodeError):
        return None


def _design_summaries(project: dict[str, str], supervisor_id: str) -> list[dict[str, Any]]:
    result = []
    for artifact in _artifacts(project, supervisor_id):
        match = re.fullmatch(r"design/([^/]+)/parsed\.json", artifact["path"])
        if match:
            content = _artifact_json(project, supervisor_id, artifact["path"])
            if isinstance(content, dict):
                result.append({"role": match.group(1), **content})
    return result


def _log_refs(project: dict[str, str], supervisor_id: str) -> list[dict[str, str]]:
    project_root = Path(project["path"]).resolve()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", supervisor_id) or supervisor_id in (".", ".."):
        return []
    runs_root = (project_root / ".factory" / "runs").resolve()
    root = (runs_root / supervisor_id).resolve()
    if not runs_root.is_relative_to(project_root) or not root.is_relative_to(runs_root) or not root.is_dir():
        return []
    refs = []
    for file in root.rglob("*"):
        if file.name not in ("stdout.log", "stderr.log") and not re.fullmatch(r"gate-[A-Za-z0-9_-]+-\d+\.log", file.name):
            continue
        try:
            if file.resolve(strict=True).is_relative_to(root):
                refs.append({"path": file.relative_to(root).as_posix(), "name": file.name, "available": "reference_only"})
        except (OSError, ValueError):
            continue
    return sorted(refs, key=lambda ref: ref["path"])
