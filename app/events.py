from __future__ import annotations

import hmac
import json
import re
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

UTC = timezone(timedelta(0), name="UTC")

_CONTEXT: ContextVar[tuple[Path, str, str | None] | None] = ContextVar("factory_event_context", default=None)
_STAGE: ContextVar[str | None] = ContextVar("factory_event_stage", default="Queue")
_ROUND: ContextVar[int | None] = ContextVar("factory_event_round", default=None)
_SECRET = re.compile(r"(?i)([\"']?[A-Za-z0-9_-]*(?:api[_-]?key|authorization|access[_-]?token|refresh[_-]?token|client[_-]?secret|token|key|password|secret|credential)[A-Za-z0-9_-]*[\"']?\s*[:=]\s*)(?:\"[^\"]*\"|'[^']*'|[^\s,;]+)")
_AUTH_HEADER = re.compile(r"(?i)([\"']?authorization[\"']?\s*[:=]\s*)(?:(?:bearer|basic)\s+)?[^\s,;]+(?:\s+[^\s,;]+)?")
_BEARER = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{8,}")
_BASIC = re.compile(r"(?i)\bBasic\s+[A-Za-z0-9+/=]{8,}")
_SK_KEY = re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b")
_GITHUB_TOKEN = re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})\b")
_AWS_ACCESS_KEY = re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")
_GOOGLE_API_KEY = re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")
_JWT = re.compile(r"\beyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\b")
_PRIVATE_KEY = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.DOTALL)
_SECRET_KEY = re.compile(r"(?i)(?:api[_-]?key|authorization|access[_-]?token|refresh[_-]?token|token|password|secret|credential|(?:^|[_-])key(?:$|[_-]))")


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def redact(value: Any) -> Any:
    if isinstance(value, str):
        value = _PRIVATE_KEY.sub("[redacted private key]", value)
        value = _AUTH_HEADER.sub(r"\1[redacted]", value)
        value = _BASIC.sub("Basic [redacted]", value)
        value = _BEARER.sub("Bearer [redacted]", value)
        value = _SECRET.sub(r"\1[redacted]", value)
        value = _SK_KEY.sub("[redacted key]", value)
        value = _GITHUB_TOKEN.sub("[redacted GitHub token]", value)
        value = _AWS_ACCESS_KEY.sub("[redacted AWS key]", value)
        value = _GOOGLE_API_KEY.sub("[redacted API key]", value)
        return _JWT.sub("[redacted JWT]", value)
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, dict):
        return {str(key): "[redacted]" if _SECRET_KEY.search(str(key)) else redact(item) for key, item in value.items()
                if str(key).lower() not in {"env", "environment", "stdout", "stderr", "log", "logs", "prompt"}}
    return value


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=20, isolation_level=None, check_same_thread=False)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA busy_timeout=20000")
    db.execute("PRAGMA journal_mode=WAL")
    return db


def initialize(path: Path, mode: str | None = None) -> None:
    db = connect(path)
    try:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS events (
                seq INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                type TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                data_json TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS events_run_seq ON events(run_id, seq);
            CREATE TABLE IF NOT EXISTS runs (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                project_name TEXT NOT NULL,
                project_path TEXT NOT NULL,
                requirement TEXT NOT NULL,
                status TEXT NOT NULL,
                stage TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                queue_position INTEGER NOT NULL,
                demo_outcome TEXT,
                supervisor_run_id TEXT,
                report_json TEXT,
                worker_pid INTEGER,
                worker_token TEXT,
                handoff_token TEXT
            );
            CREATE INDEX IF NOT EXISTS runs_queue ON runs(status, queue_position, created_at);
            CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        """)
        columns = {row["name"] for row in db.execute("PRAGMA table_info(runs)")}
        if "worker_pid" not in columns:
            db.execute("ALTER TABLE runs ADD COLUMN worker_pid INTEGER")
        if "worker_token" not in columns:
            db.execute("ALTER TABLE runs ADD COLUMN worker_token TEXT")
        if "handoff_token" not in columns:
            db.execute("ALTER TABLE runs ADD COLUMN handoff_token TEXT")
        if mode is not None:
            existing_mode = db.execute("SELECT value FROM metadata WHERE key='mode'").fetchone()
            if existing_mode and existing_mode["value"] != mode:
                raise ValueError(f"Refusing to open a {existing_mode['value']} event database in {mode} mode")
            db.execute("INSERT OR IGNORE INTO metadata(key,value) VALUES('mode',?)", (mode,))
    finally:
        db.close()


@contextmanager
def event_context(db_path: Path | str | None, run_id: str | None, queue_id: str | None = None) -> Iterator[None]:
    if not db_path or not run_id:
        yield
        return
    path = Path(db_path).resolve()
    initialize(path)
    token = _CONTEXT.set((path, run_id, queue_id))
    stage_token = _STAGE.set("Queue")
    round_token = _ROUND.set(None)
    try:
        yield
    finally:
        _ROUND.reset(round_token)
        _STAGE.reset(stage_token)
        _CONTEXT.reset(token)


def current_context() -> tuple[Path, str, str | None] | None:
    return _CONTEXT.get()


def register_cli_run(path: Path, run_id: str, project: Path, requirement: str, pid: int, token: str | None,
                     handoff_token: str | None = None, *, require_handoff: bool = False) -> None:
    """Create the direct-CLI dashboard row or attach a queued row to its supervisor process."""
    initialize(path, mode="live")
    now = utc_now()
    db = connect(path)
    try:
        db.execute("BEGIN IMMEDIATE")
        existing = db.execute("SELECT id,status,project_path,requirement,handoff_token FROM runs WHERE id=?", (run_id,)).fetchone()
        if existing:
            if existing["status"] in ("completed", "blocked", "interrupted", "orphaned"):
                raise ValueError("Run ID already belongs to a terminal run")
            if (existing["status"] not in ("queued", "starting") or
                    Path(existing["project_path"]).resolve() != project.resolve() or
                    existing["requirement"] != redact(requirement) or
                    not handoff_token or not existing["handoff_token"] or
                    not hmac.compare_digest(existing["handoff_token"], handoff_token)):
                raise ValueError("Run ID is not a valid dashboard handoff")
            db.execute("UPDATE runs SET worker_pid=?,worker_token=?,updated_at=? WHERE id=?", (pid, token, now, run_id))
        else:
            if require_handoff or handoff_token:
                raise ValueError("Dashboard handoff does not exist")
            position = int(db.execute("SELECT COALESCE(MAX(queue_position),0)+1 FROM runs WHERE status='queued'").fetchone()[0])
            project_id = re.sub(r"[^a-zA-Z0-9_-]+", "-", project.name.lower()).strip("-") or "project"
            db.execute("INSERT INTO runs(id,project_id,project_name,project_path,requirement,status,stage,created_at,updated_at,queue_position,worker_pid,worker_token) VALUES(?,?,?,?,?,'queued','Queue',?,?,?,?,?)",
                       (run_id, project_id, project.name, str(project.resolve()), redact(requirement), now, now, position, pid, token))
            data = {"status": "queued", "stage": "Queue", "round": None, "attempt": "run", "queue_id": run_id}
            add_event(db, run_id, "run_created", data)
            add_event(db, run_id, "run_queued", data)
        db.commit()
    finally:
        db.close()


def assert_no_orphaned_run(path: Path, project: Path, current_run_id: str) -> None:
    db = connect(path)
    try:
        row = db.execute("SELECT id FROM runs WHERE status='orphaned' AND project_path=? LIMIT 1",
                         (str(project.resolve()),)).fetchone()
    finally:
        db.close()
    if row:
        raise RuntimeError("A prior run has an unresolved orphan state for this checkout; refusing concurrent writes")


def emit(event_type: str, data: dict[str, Any] | None = None) -> None:
    context = _CONTEXT.get()
    if context is None:
        return
    path, run_id, queue_id = context
    original = data or {}
    if event_type == "stage_entered" and original.get("stage"):
        _STAGE.set(original["stage"])
    if event_type == "round_incremented" and type(original.get("round")) is int:
        _ROUND.set(original["round"])
    payload = redact(original)
    payload.setdefault("stage", _STAGE.get())
    payload.setdefault("round", _ROUND.get())
    payload.setdefault("attempt", payload.get("phase") or "run")
    if queue_id:
        payload.setdefault("queue_id", queue_id)
    db = connect(path)
    try:
        db.execute("BEGIN IMMEDIATE")
        run = db.execute("SELECT status FROM runs WHERE id = ?", (run_id,)).fetchone()
        if run is not None and run["status"] in ("completed", "blocked", "interrupted", "orphaned") and event_type not in ("run_interrupted", "run_completed"):
            db.rollback()
            return
        now = utc_now()
        if run is not None:
            from .projector import project_event
            row = db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
            updated = project_event(dict(row), event_type, payload, now)
            payload["status"] = updated["status"]
            payload["stage"] = updated["stage"]
            db.execute("UPDATE runs SET status=?,stage=?,updated_at=?,supervisor_run_id=COALESCE(?,supervisor_run_id),report_json=COALESCE(?,report_json) WHERE id=?",
                       (updated["status"], updated["stage"], now, updated.get("supervisor_run_id"), updated.get("report_json"), run_id))
        db.execute("INSERT INTO events(run_id,type,timestamp,data_json) VALUES(?,?,?,?)",
                    (run_id, event_type, now, json.dumps(payload, ensure_ascii=False, separators=(",", ":"))))
        db.commit()
    finally:
        db.close()


def add_event(db: sqlite3.Connection, run_id: str, event_type: str, data: dict[str, Any] | None = None) -> int:
    now = utc_now()
    cursor = db.execute("INSERT INTO events(run_id,type,timestamp,data_json) VALUES(?,?,?,?)",
                         (run_id, event_type, now, json.dumps(redact(data or {}), ensure_ascii=False, separators=(",", ":"))))
    return int(cursor.lastrowid)


def events_for(path: Path, run_id: str, after: int = 0, limit: int = 1000) -> list[dict[str, Any]]:
    db = connect(path)
    try:
        rows = db.execute("SELECT seq,run_id,type,timestamp,data_json FROM events WHERE run_id=? AND seq>? ORDER BY seq LIMIT ?",
                          (run_id, after, limit)).fetchall()
    finally:
        db.close()
    return [{"id": row["seq"], "seq": row["seq"], "run_id": row["run_id"], "type": row["type"],
             "timestamp": row["timestamp"], "data": json.loads(row["data_json"])} for row in rows]

