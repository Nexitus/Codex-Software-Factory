from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

UTC = timezone(timedelta(0), name="UTC")


class CheckoutBusy(RuntimeError):
    pass


class CheckoutQuarantined(RuntimeError):
    pass


def canonical_checkout(project: Path) -> Path:
    cp = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=project, capture_output=True, text=True, encoding="utf-8", check=False)
    if cp.returncode:
        raise ValueError("Project must be a Git checkout")
    return Path(cp.stdout.strip()).resolve()


def _confined_path(root: Path, path: Path, label: str) -> Path:
    try:
        resolved = path.resolve(strict=False)
    except (OSError, RuntimeError) as exc:
        raise CheckoutQuarantined(f"Cannot resolve checkout {label} path: {exc}") from exc
    if not resolved.is_relative_to(root):
        raise CheckoutQuarantined(f"The checkout {label} path resolves outside the checkout")
    return resolved


def confined_checkout_path(checkout: Path, path: Path, label: str) -> Path:
    """Resolve a supervisor-owned path and reject it if it escapes the checkout."""
    return _confined_path(checkout.resolve(strict=True), path, label)


def preflight_checkout_state(checkout: Path, *, default_event_db: bool = True) -> None:
    """Check every supervisor-owned target path before the first state write."""
    root = checkout.resolve(strict=True)
    factory_path = root / ".factory"
    factory_dir = _confined_path(root, factory_path, ".factory")
    if factory_path.exists() and not factory_path.is_dir():
        raise CheckoutQuarantined("The checkout .factory path is not a directory")

    runs_path = factory_dir / "runs"
    _confined_path(root, runs_path, ".factory/runs")
    if runs_path.exists() and not runs_path.is_dir():
        raise CheckoutQuarantined("The checkout .factory/runs path is not a directory")

    for name in ("active-run.json", "checkout.lock"):
        path = factory_dir / name
        _confined_path(root, path, f".factory/{name}")
        if path.exists() and (path.is_symlink() or not path.is_file()):
            raise CheckoutQuarantined(f"The checkout .factory/{name} path is not a regular file")

    if default_event_db:
        event_db = factory_dir / "dashboard.sqlite3"
        _confined_path(root, event_db, ".factory/dashboard.sqlite3")
        if event_db.exists() and (event_db.is_symlink() or not event_db.is_file()):
            raise CheckoutQuarantined("The checkout .factory/dashboard.sqlite3 path is not a regular file")


def _factory_dir(checkout: Path) -> Path:
    root = checkout.resolve(strict=True)
    candidate = root / ".factory"
    _confined_path(root, candidate, ".factory")
    if candidate.exists() and not candidate.is_dir():
        raise CheckoutQuarantined("The checkout .factory path is not a directory")
    candidate.mkdir(parents=True, exist_ok=True)
    return _confined_path(root, candidate, ".factory")


class CheckoutClaim:
    """Durable fail-closed marker for a supervisor that might have orphaned descendants.

    The advisory OS lock prevents simultaneous normal runs. The marker survives a hard
    process exit, when descendants may have escaped the lock owner's lifetime.
    """

    def __init__(self, checkout: Path, run_id: str, pid: int, birth: str | None):
        self.path = _factory_dir(checkout) / "active-run.json"
        self.run_id = run_id
        self.pid = pid
        self.birth = birth
        self.owned = False

    def acquire(self) -> CheckoutClaim:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"run_id": self.run_id, "pid": self.pid, "process_birth": self.birth,
                   "created_at": datetime.now(UTC).isoformat()}
        try:
            descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as exc:
            raise CheckoutQuarantined("Checkout has an unresolved active-run marker; verify all prior workers are gone before removing it") from exc
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump(payload, stream, separators=(",", ":"))
                stream.flush()
                os.fsync(stream.fileno())
        except BaseException:
            try:
                self.path.unlink(missing_ok=True)
            except OSError:
                pass
            raise
        self.owned = True
        return self

    def release_after_worker_exit(self) -> None:
        if not self.owned or self.path.is_symlink():
            return
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            if payload.get("run_id") == self.run_id and payload.get("pid") == self.pid and payload.get("process_birth") == self.birth:
                self.path.unlink(missing_ok=True)
                self.owned = False
        except (OSError, ValueError):
            # A malformed marker must remain in place for explicit operator inspection.
            return


def claim_checkout(project: Path, run_id: str, pid: int, birth: str | None) -> CheckoutClaim:
    return CheckoutClaim(canonical_checkout(project), run_id, pid, birth).acquire()


@contextmanager
def checkout_lock(project: Path, *, wait: bool = False) -> Iterator[None]:
    checkout = canonical_checkout(project)
    lock_path = _factory_dir(checkout) / "checkout.lock"
    if lock_path.is_symlink():
        raise CheckoutQuarantined("Checkout lock path is a symlink; refusing an unsafe lock")
    handle = lock_path.open("a+b")
    try:
        while True:
            try:
                if sys.platform == "win32":
                    import msvcrt
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError as exc:
                if not wait:
                    raise CheckoutBusy(f"A factory run already holds the checkout lock for {checkout}") from exc
                time.sleep(0.25)
        yield
    finally:
        try:
            if sys.platform == "win32":
                import msvcrt
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        handle.close()
