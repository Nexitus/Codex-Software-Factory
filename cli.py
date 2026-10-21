"""Help/version and project initialization entry point."""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sqlite3
import sys
import uuid
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

try:
    _VERSION = version("codex-software-factory")
except PackageNotFoundError:
    _VERSION = "0.6.0"

if __package__:
    from . import factory
    from .app.checkout_lock import preflight_checkout_state
    from .app.projector import project_run
    from .project_setup import ALL_HARNESSES, initialize
else:
    import factory
    from app.checkout_lock import preflight_checkout_state
    from app.projector import project_run
    from project_setup import ALL_HARNESSES, initialize

_RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
_MAX_REPORT_BYTES = 10_000_000


def _probe_state(project: Path) -> str | None:
    state_dir = project / ".factory"
    created_dirs = []
    probes = []
    error = None
    try:
        preflight_checkout_state(project)
        for directory in (state_dir, state_dir / "runs"):
            if not directory.exists():
                directory.mkdir()
                created_dirs.append(directory)
            if not directory.resolve(strict=True).is_relative_to(project):
                raise OSError(f"The {directory.relative_to(project)} state path resolves outside the checkout")
            probe = directory / f".doctor-probe-{uuid.uuid4().hex}"
            with probe.open("x", encoding="utf-8"):
                probes.append(probe)
    except (OSError, RuntimeError, ValueError) as exc:
        error = str(exc)
    finally:
        for probe in reversed(probes):
            try:
                if probe.exists() and probe.resolve(strict=True).is_relative_to(project):
                    probe.unlink()
            except (OSError, RuntimeError, ValueError) as exc:
                error = error or f"could not remove transient probe: {exc}"
        for directory in reversed(created_dirs):
            try:
                if directory.exists() and directory.resolve(strict=True).is_relative_to(project):
                    directory.rmdir()
            except OSError:
                pass
    return error


def _executable_available(project: Path, executable: str) -> bool:
    path = Path(executable)
    if path.is_absolute() or path.name != executable or "/" in executable or "\\" in executable:
        path = path if path.is_absolute() else project / path
        return shutil.which(str(path)) is not None
    return shutil.which(executable) is not None


def doctor(project: Path, config: Path | None = None) -> int:
    try:
        project = factory.canonical_checkout(project.resolve(strict=True))
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"Project: BLOCKED: must be an existing Git checkout ({exc})")
        return 2

    config_path = (config if config is not None else project / "factory.config.json").resolve()
    print(f"Project: {project}")
    print(f"Config: {config_path}")
    ready = True
    try:
        cfg = json.loads(config_path.read_text(encoding="utf-8"))
        factory.ensure_config(cfg)
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError, factory.FactoryFailure) as exc:
        print(f"Config and gates: BLOCKED: {exc}")
        ready = False
        cfg = None

    if cfg is not None:
        for gate in cfg["required_gates"]:
            for argv in cfg["commands"][gate]:
                executable = argv[0]
                if not _executable_available(project, executable):
                    print(f"Gate '{gate}': BLOCKED: executable not found: {executable}")
                    ready = False
        for provider in dict.fromkeys(cfg["providers"].values()):
            executable = {"codex": "codex", "claude": "claude"}[provider]
            if not shutil.which(executable):
                print(f"{provider} CLI: BLOCKED: executable not found: {executable}")
                ready = False

    state_error = _probe_state(project)
    if state_error:
        print(f"State paths: BLOCKED: {state_error}")
        ready = False
    else:
        print("State paths: writable (temporary probe created and removed)")

    if ready:
        print("Readiness: READY (local checks only; provider authentication and gate results were not checked)")
        return 0
    print("Readiness: NOT READY")
    return 2


def _read_run_file(project: Path, supervisor_id: str, filename: str) -> tuple[Path, dict | None, str | None]:
    runs_root = project / ".factory" / "runs"
    run_dir = runs_root / supervisor_id
    path = run_dir / filename
    try:
        if not _RUN_ID.fullmatch(supervisor_id):
            return path, None, "invalid supervisor run ID"
        resolved_runs = runs_root.resolve(strict=True)
        resolved_run = run_dir.resolve(strict=True)
        if not resolved_runs.is_relative_to(project) or not resolved_run.is_relative_to(resolved_runs):
            return path, None, "evidence path resolves outside the checkout"
        resolved = path.resolve(strict=True)
        if not resolved.is_relative_to(resolved_run) or not resolved.is_file():
            return path, None, "evidence path is not a regular file inside its run directory"
        if resolved.stat().st_size > _MAX_REPORT_BYTES:
            return path, None, "evidence file exceeds the 10 MB limit"
        with resolved.open("rb") as stream:
            raw = stream.read(_MAX_REPORT_BYTES + 1)
        if len(raw) > _MAX_REPORT_BYTES:
            return path, None, "evidence file exceeds the 10 MB limit"
        value = json.loads(raw.decode("utf-8"))
        if not isinstance(value, dict):
            return path, None, "evidence must be a JSON object"
        return path, value, None
    except FileNotFoundError:
        return path, None, None
    except (OSError, RuntimeError, ValueError, UnicodeError, json.JSONDecodeError) as exc:
        return path, None, str(exc)


def _print_status(run_id: str, state: str, evidence: Path | None, detail: str | None = None,
                  result: int = 0) -> int:
    print(f"Run ID: {run_id}")
    print(f"State: {state}")
    print(f"Evidence: {evidence if evidence is not None else 'none'}")
    if detail:
        print(f"Details: {detail}")
    return result


def _legacy_status(project: Path) -> int:
    runs_root = project / ".factory" / "runs"
    try:
        resolved_runs = runs_root.resolve(strict=True)
        if not resolved_runs.is_relative_to(project):
            return _print_status("none", "malformed", runs_root, "legacy evidence path resolves outside the checkout", 2)
        run_dirs = [path for path in runs_root.iterdir() if path.is_dir()]
    except FileNotFoundError:
        print(f"Project: {project}")
        print("No runs found.")
        return 0
    except (OSError, RuntimeError, ValueError) as exc:
        return _print_status("none", "malformed", runs_root, str(exc), 2)
    if not run_dirs:
        print(f"Project: {project}")
        print("No runs found.")
        return 0

    run_dir = max(run_dirs, key=lambda path: path.name)
    supervisor_id = run_dir.name
    delivery_path, delivery, delivery_error = _read_run_file(project, supervisor_id, "DELIVERY.json")
    error_path, error_report, error_error = _read_run_file(project, supervisor_id, "ERROR.json")
    dry_path, dry_run, dry_error = _read_run_file(project, supervisor_id, "dry-run.json")
    if delivery_error or error_error or dry_error:
        evidence = delivery_path if delivery_error else error_path if error_error else dry_path
        detail = delivery_error or error_error or dry_error
        return _print_status(supervisor_id, "malformed", evidence, detail, 2)
    if delivery is not None and error_report is not None:
        return _print_status(supervisor_id, "malformed", delivery_path,
                             "both DELIVERY.json and ERROR.json exist", 2)
    if dry_run is not None:
        if delivery is not None or error_report is not None:
            return _print_status(supervisor_id, "malformed", dry_path,
                                 "preflight artifact conflicts with delivery or error report", 2)
        if (not isinstance(dry_run.get("planned_roles"), list) or
                not all(isinstance(role, str) for role in dry_run["planned_roles"]) or
                not isinstance(dry_run.get("required_gates"), list) or
                not all(isinstance(gate, str) for gate in dry_run["required_gates"]) or
                not isinstance(dry_run.get("note"), str)):
            return _print_status(supervisor_id, "malformed", dry_path,
                                 "preflight artifact does not match the supervisor report shape", 2)
        return _print_status(supervisor_id, "preflight", dry_path)
    report = delivery or error_report
    evidence = delivery_path if delivery is not None else error_path if error_report is not None else delivery_path
    if report is None:
        return _print_status(supervisor_id, "missing evidence", evidence,
                             "legacy run has no delivery or error report", 2)
    if report.get("status") == "blocked":
        return _print_status(supervisor_id, "blocked", evidence)
    if report.get("status") == "verified_candidate":
        return _print_status(supervisor_id, "missing evidence", evidence,
                             "legacy candidate has no persisted delivery_verified event", 2)
    return _print_status(supervisor_id, "malformed", evidence, "unrecognized report status", 2)


def _latest_supervisor_id(project: Path) -> str | None:
    runs_root = project / ".factory" / "runs"
    try:
        resolved_runs = runs_root.resolve(strict=True)
    except FileNotFoundError:
        return None
    if not resolved_runs.is_relative_to(project):
        raise ValueError("runs path resolves outside the checkout")
    run_dirs = [path for path in runs_root.iterdir() if path.is_dir()]
    return max((path.name for path in run_dirs), default=None)


def status(project: Path) -> int:
    try:
        project = factory.canonical_checkout(project.resolve(strict=True))
        preflight_checkout_state(project)
    except (OSError, RuntimeError, ValueError, factory.CheckoutQuarantined) as exc:
        return _print_status("none", "malformed", project / ".factory", str(exc), 2)

    database = project / ".factory" / "dashboard.sqlite3"
    if database.is_symlink():
        return _print_status("none", "malformed", database, "event database is a symlink", 2)
    if not database.is_file():
        return _legacy_status(project)

    try:
        db = sqlite3.connect(f"{database.resolve(strict=True).as_uri()}?mode=ro", uri=True, timeout=5)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA query_only=ON")
        row = db.execute("SELECT * FROM runs WHERE project_path=? ORDER BY created_at DESC,rowid DESC LIMIT 1",
                         (str(project),)).fetchone()
        if row is None:
            db.close()
            return _legacy_status(project)
        run = dict(row)
        raw_events = db.execute("SELECT seq,type,timestamp,data_json FROM events WHERE run_id=? ORDER BY seq",
                                (run["id"],)).fetchall()
        events = []
        for event in raw_events:
            data = json.loads(event["data_json"])
            if not isinstance(data, dict):
                raise TypeError("event data must be a JSON object")
            events.append({"id": event["seq"], "seq": event["seq"], "run_id": run["id"],
                           "type": event["type"], "timestamp": event["timestamp"], "data": data})
        projected = project_run(run, events)
    except (OSError, RuntimeError, ValueError, sqlite3.Error, KeyError, TypeError) as exc:
        try:
            db.close()
        except (UnboundLocalError, sqlite3.Error):
            pass
        return _print_status("unknown", "malformed", database, str(exc), 2)
    finally:
        try:
            db.close()
        except (UnboundLocalError, sqlite3.Error):
            pass

    if run["status"] not in (projected["status"], "starting" if projected["status"] == "queued" else None):
        return _print_status(run["id"], "malformed", database, "event history conflicts with the stored run state", 2)

    supervisor_id = run.get("supervisor_run_id") or projected.get("supervisor_run_id")
    if supervisor_id is not None and not isinstance(supervisor_id, str):
        return _print_status(run["id"], "malformed", database, "invalid supervisor run ID", 2)
    try:
        latest_supervisor_id = _latest_supervisor_id(project)
    except (OSError, RuntimeError, ValueError) as exc:
        return _print_status(run["id"], "malformed", project / ".factory" / "runs", str(exc), 2)
    if supervisor_id and latest_supervisor_id and latest_supervisor_id > supervisor_id:
        return _legacy_status(project)
    delivery_path = project / ".factory" / "runs" / (supervisor_id or "") / "DELIVERY.json"
    error_path = project / ".factory" / "runs" / (supervisor_id or "") / "ERROR.json"
    delivery = error_report = None
    if supervisor_id:
        delivery_path, delivery, delivery_error = _read_run_file(project, supervisor_id, "DELIVERY.json")
        error_path, error_report, error_error = _read_run_file(project, supervisor_id, "ERROR.json")
        if delivery_error or error_error:
            return _print_status(run["id"], "malformed", delivery_path if delivery_error else error_path,
                                 delivery_error or error_error, 2)
        if delivery is not None and error_report is not None:
            return _print_status(run["id"], "malformed", delivery_path,
                                 "both DELIVERY.json and ERROR.json exist", 2)

    delivery_events = [event for event in events if event["type"] == "delivery_verified" and
                       event["data"].get("delivery_status") == "verified_candidate"]
    conflicting_terminal = any(
        event["type"] in ("run_blocked", "run_interrupted", "run_orphaned") or
        (event["type"] == "delivery_verified" and event["data"].get("delivery_status") != "verified_candidate") or
        (event["type"] == "run_completed" and event["data"].get("delivery_status") not in
         ("verified_candidate", "dry_run"))
        for event in events
    )
    if delivery_events and conflicting_terminal:
        return _print_status(run["id"], "malformed", delivery_path,
                             "conflicting terminal events prevent verified status", 2)

    evidence = delivery_path if delivery is not None else error_path if error_report is not None else database
    if delivery is not None and delivery.get("status") == "verified_candidate":
        if not delivery_events or projected.get("delivery_status") != "verified_candidate":
            return _print_status(run["id"], "malformed", delivery_path,
                                 "candidate report has no matching delivery_verified event", 2)
        return _print_status(run["id"], "verified candidate", delivery_path)
    if delivery is not None and delivery.get("status") == "blocked":
        if projected.get("status") != "blocked":
            return _print_status(run["id"], "malformed", delivery_path,
                                 "blocked report conflicts with event history", 2)
        return _print_status(run["id"], "blocked", delivery_path)
    if error_report is not None:
        if error_report.get("status") != "blocked" or projected.get("status") != "blocked":
            return _print_status(run["id"], "malformed", error_path,
                                 "error report conflicts with event history", 2)
        return _print_status(run["id"], "blocked", error_path)
    if delivery_events:
        return _print_status(run["id"], "missing evidence", delivery_path,
                             "delivery_verified event has no matching DELIVERY.json", 2)
    if delivery is not None:
        return _print_status(run["id"], "malformed", delivery_path, "unrecognized report status", 2)
    if projected.get("delivery_status") == "dry_run":
        dry_path, dry_run, dry_error = _read_run_file(project, supervisor_id, "dry-run.json") if supervisor_id else (None, None, None)
        if dry_error:
            return _print_status(run["id"], "malformed", dry_path, dry_error, 2)
        if dry_run is None:
            return _print_status(run["id"], "missing evidence", dry_path,
                                 "preflight event has no dry-run.json", 2)
        return _print_status(run["id"], "preflight", dry_path)
    if projected.get("status") == "running":
        return _print_status(run["id"], "running", evidence)
    if projected.get("status") == "interrupted":
        return _print_status(run["id"], "interrupted", evidence)
    if projected.get("status") == "orphaned":
        return _print_status(run["id"], "missing evidence", delivery_path,
                             "orphaned run has no persisted verification event", 2)
    if projected.get("status") == "blocked":
        if supervisor_id:
            return _print_status(run["id"], "missing evidence", delivery_path,
                                 "blocked run has no DELIVERY.json or ERROR.json", 2)
        return _print_status(run["id"], "blocked", database)
    if projected.get("status") in ("queued", "starting"):
        return _print_status(run["id"], "queued", evidence)
    return _print_status(run["id"], "missing evidence", evidence,
                         "run history has no recognized terminal evidence", 2)


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="backslashreplace")
            except (OSError, ValueError):
                pass
    cli_args = list(sys.argv[1:] if argv is None else argv)
    if cli_args[:1] == ["run"]:
        supervisor_args = cli_args[1:]
        if supervisor_args[:1] == ["--"]:
            supervisor_args = supervisor_args[1:]
        try:
            if __package__:
                from . import factory
            else:
                import factory
            return factory.main(supervisor_args)
        except SystemExit as error:
            return int(error.code or 0)
        except (ImportError, OSError, ValueError) as error:
            print(f"software-factory run: BLOCKED: {error}", file=sys.stderr)
            return 2
    parser = argparse.ArgumentParser(
        prog="software-factory",
        description="Command-line interface for Codex Software Factory.",
    )
    parser.add_argument("--version", action="version", version=_VERSION)
    commands = parser.add_subparsers(dest="command")
    init = commands.add_parser("init", help="initialize an existing Git checkout")
    init.add_argument("--project", type=Path, default=Path.cwd(), help="checkout to initialize")
    init.add_argument("--harness", choices=ALL_HARNESSES, action="append",
                      help="install a selected host skill (repeatable; defaults to all)")
    doctor_parser = commands.add_parser("doctor", help="check local project readiness without executing work")
    doctor_parser.add_argument("--project", type=Path, default=Path.cwd(), help="checkout to inspect")
    doctor_parser.add_argument("--config", type=Path, help="configuration file; defaults to <project>/factory.config.json")
    commands.add_parser("run", help="run the supervised workflow")
    status_parser = commands.add_parser("status", help="show the latest run and its evidence")
    status_parser.add_argument("--project", type=Path, default=Path.cwd(), help="checkout to inspect")
    args = parser.parse_args(cli_args)
    if args.command is None:
        parser.print_help()
        return 0
    if args.command == "init":
        try:
            written = initialize(args.project, args.harness or list(ALL_HARNESSES))
        except (OSError, ValueError) as error:
            print(f"software-factory init: {error}", file=sys.stderr)
            return 2
        if written:
            print("Initialized project files:")
            for path in written:
                print(path)
        else:
            print("Project already initialized; no changes made.")
    elif args.command == "doctor":
        return doctor(args.project, args.config)
    elif args.command == "status":
        return status(args.project)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
