from __future__ import annotations

import json
from typing import Any

STAGES = ("Queue", "Planning", "Design", "Build", "Review", "Repair", "Ready", "Blocked")
TERMINAL = {"completed", "blocked", "interrupted", "orphaned"}


def project_event(run: dict[str, Any], event_type: str, data: dict[str, Any], timestamp: str) -> dict[str, Any]:
    """Apply one persisted event to the compact run row deterministically."""
    status, stage = run["status"], run["stage"]
    supervisor_run_id, report_json = None, None
    if status in TERMINAL:
        return {"status": status, "stage": stage}
    if event_type == "run_started":
        status, stage = "running", "Planning"
        supervisor_run_id = data.get("supervisor_run_id")
    elif event_type == "stage_entered" and data.get("stage") in STAGES and data.get("stage") != "Ready":
        stage = data["stage"]
    elif event_type == "delivery_verified":
        if data.get("delivery_status") == "verified_candidate":
            status, stage = "completed", "Ready"
            report_json = json.dumps(data, ensure_ascii=False)
    elif event_type == "run_blocked":
        status, stage = "blocked", "Blocked"
        supervisor_run_id = data.get("supervisor_run_id")
        report_json = json.dumps(data, ensure_ascii=False)
    elif event_type == "run_interrupted":
        status, stage = "interrupted", "Blocked"
    elif event_type == "run_orphaned":
        status, stage = "orphaned", "Blocked"
    elif event_type == "run_completed" and data.get("delivery_status") == "dry_run":
        status = "completed"
    return {"status": status, "stage": stage, "supervisor_run_id": supervisor_run_id, "report_json": report_json}


def project_run(row: dict[str, Any], events: list[dict[str, Any]]) -> dict[str, Any]:
    """Build dashboard details solely from the ordered event log."""
    result = dict(row)
    result.update({"stage": "Queue", "status": "queued", "round": 0, "max_rounds": None,
                   "agents": {}, "gates": {}, "findings": [], "history": [], "demo_plan": None, "demo_design": []})
    for event in events:
        kind, data = event["type"], event["data"]
        result["history"].append(event)
        if result["status"] in TERMINAL:
            continue
        result.update(project_event(result, kind, data, event["timestamp"]))
        if kind == "run_queued":
            result["status"] = "queued"
            result["stage"] = "Queue"
        elif kind == "stage_entered" and data.get("stage") in STAGES and data.get("stage") != "Ready":
            result["stage"] = data["stage"]
        elif kind == "run_started":
            result["max_rounds"] = data.get("max_rounds")
        elif kind == "demo_context" and data.get("synthetic") is True:
            result["demo_plan"] = data.get("plan")
            result["demo_design"] = data.get("design", [])
        elif kind == "agent_started":
            result["agents"][data.get("role", "unknown")] = {**data, "status": "running"}
        elif kind in ("agent_succeeded", "agent_failed", "agent_timed_out"):
            role = data.get("role", "unknown")
            previous = result["agents"].get(role, {})
            status = ("failed" if data.get("verdict") == "fail" else "passed" if data.get("verdict") == "pass"
                      else "not_applicable" if data.get("verdict") == "not_applicable" else "succeeded") if kind == "agent_succeeded" else "timed_out" if kind == "agent_timed_out" else "failed"
            result["agents"][role] = {**previous, **data, "status": status}
        elif kind == "gate_started":
            result["gates"][data.get("name", "unknown")] = {**data, "pass": None, "status": "running"}
        elif kind in ("gate_passed", "gate_failed"):
            name = data.get("name", "unknown")
            result["gates"][name] = {**result["gates"].get(name, {}), **data,
                                     "pass": kind == "gate_passed", "status": "passed" if kind == "gate_passed" else "failed"}
        elif kind == "finding_recorded":
            result["findings"].append(data)
        elif kind == "round_incremented":
            result["round"] = data.get("round", result["round"] + 1)
        elif kind == "delivery_verified":
            if data.get("delivery_status") == "verified_candidate":
                result["status"], result["stage"], result["delivery_status"] = "completed", "Ready", "verified_candidate"
                result["delivery"] = data
        elif kind == "run_blocked":
            result["status"], result["stage"], result["delivery_status"] = "blocked", "Blocked", "blocked"
            result["blockers"] = data.get("blockers", [])
            if data.get("error_summary"):
                result["error_summary"] = data["error_summary"]
        elif kind == "run_interrupted":
            result["status"], result["stage"], result["delivery_status"] = "interrupted", "Blocked", "interrupted"
        elif kind == "run_orphaned":
            result["status"], result["stage"], result["delivery_status"] = "orphaned", "Blocked", "orphaned"
        elif kind == "run_completed" and data.get("delivery_status") == "dry_run":
            result["status"], result["delivery_status"] = "completed", "dry_run"
    expected_phase = {"Planning": "plan", "Design": "design", "Build": "build", "Review": "review",
                      "Repair": "repair", "Ready": "review", "Blocked": "review"}.get(result["stage"])
    for agent in result["agents"].values():
        agent["current"] = bool(agent.get("phase") == expected_phase and
                                (expected_phase != "review" or agent.get("round") == result["round"]))
    current_round = result["round"]
    result["active_findings"] = [finding for finding in result["findings"] if finding.get("round") == current_round]
    result["finding_counts"] = {level: sum(f.get("severity") == level for f in result["active_findings"])
                                for level in ("critical", "high", "medium", "low")}
    result["gates"] = list(result["gates"].values())
    result["agents"] = list(result["agents"].values())
    return result
