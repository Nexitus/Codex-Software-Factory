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
    cp = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=project, capture_output=True, text=True, check=False)
    if cp.returncode:
        raise ValueError("Project must be a Git checkout")
    return Path(cp.stdout.strip()).resolve()


def _factory_dir(checkout: Path) -> Path:
    root = checkout.resolve(strict=True)
    candidate = root / ".factory"
    candidate.mkdir(parents=True, exist_ok=True)
    resolved = candidate.resolve(strict=True)
    if not resolved.is_relative_to(root):
        raise CheckoutQuarantined("The checkout .factory path resolves outside the checkout")
    return resolved


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
