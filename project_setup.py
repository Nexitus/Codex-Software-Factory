from __future__ import annotations

import os
from pathlib import Path
import stat
import subprocess
import tempfile

ALL_HARNESSES = ("codex", "claude", "opencode")
_IGNORE_START = b"# >>> codex-software-factory managed >>>"
_IGNORE_END = b"# <<< codex-software-factory managed <<<"


def _git_root(project: Path) -> Path:
    try:
        requested = Path(project).expanduser().resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise ValueError(f"project path is not available: {project}") from error
    if not requested.is_dir():
        raise ValueError(f"project path is not a directory: {requested}")
    try:
        result = subprocess.run(
            ["git", "-c", "core.quotepath=false", "-C", str(requested),
             "rev-parse", "--show-toplevel"],
            capture_output=True, check=True, text=True, encoding="utf-8",
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise ValueError(f"project is not inside an existing Git checkout: {requested}") from error
    try:
        return Path(result.stdout.rstrip("\r\n")).resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise ValueError(f"Git returned an invalid checkout root for {requested}") from error


def _target(root: Path, relative: Path, *, allow_directory: bool = False) -> Path:
    path = root / relative
    try:
        path.resolve(strict=False).relative_to(root)
    except (OSError, RuntimeError, ValueError) as error:
        raise ValueError(f"output path escapes the checkout: {relative}") from error
    parent = path.parent
    while parent != root:
        if os.path.lexists(parent) and not parent.is_dir():
            raise ValueError(f"output parent is not a directory: {parent.relative_to(root)}")
        parent = parent.parent
    if os.path.lexists(path) and path.is_dir() and not allow_directory:
        raise ValueError(f"output path is a directory: {relative}")
    if os.path.lexists(path) and not allow_directory and not path.is_file():
        raise ValueError(f"output path is not a regular file: {relative}")
    return path


def _ignored(root: Path) -> bool:
    result = subprocess.run(
        ["git", "-C", str(root), "check-ignore", "--quiet", "--", ".factory/"],
        capture_output=True, check=False,
    )
    if result.returncode not in (0, 1):
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise ValueError(f"Git could not check whether .factory is ignored: {detail}")
    return result.returncode == 0


def _ignore_with_factory_rule(original: bytes) -> bytes:
    if _IGNORE_START in original or _IGNORE_END in original:
        raise ValueError("existing .gitignore contains a conflicting factory marker")
    newline = b"\r\n" if b"\r\n" in original and original.count(b"\r\n") == original.count(b"\n") else b"\n"
    block = newline.join((_IGNORE_START, b".factory/", _IGNORE_END, b""))
    separator = newline if original and not original.endswith((b"\n", b"\r")) else b""
    return original + separator + block


def _stage(destination: Path, content: bytes) -> Path:
    descriptor, name = tempfile.mkstemp(prefix=".codex-factory-init-", dir=destination.parent)
    staged = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(staged, 0o644)
    except BaseException:
        staged.unlink(missing_ok=True)
        raise
    return staged


def _identity(path: Path) -> tuple[int, int]:
    info = path.lstat()
    return info.st_dev, info.st_ino


def _rollback(paths: list[tuple[Path, tuple[int, int]]]) -> list[str]:
    failures = []
    for path, identity in reversed(paths):
        try:
            if _identity(path) == identity:
                path.unlink()
        except OSError as error:
            failures.append(f"{path}: {error}")
    return failures


def _cleanup(staged: dict[Path, Path], directories: list[Path]) -> list[str]:
    failures = []
    for path in staged.values():
        try:
            path.unlink(missing_ok=True)
        except OSError as error:
            failures.append(f"{path}: {error}")
    for directory in reversed(directories):
        try:
            directory.rmdir()
        except OSError as error:
            if not directory.exists():
                continue
            try:
                next(directory.iterdir())
            except StopIteration:
                failures.append(f"{directory}: {error}")
            except OSError as list_error:
                failures.append(f"{directory}: {list_error}")
    return failures


def _created_directories(root: Path, target: Path, created: list[Path]) -> None:
    missing = []
    parent = target.parent
    while parent != root and not os.path.lexists(parent):
        missing.append(parent)
        parent = parent.parent
    for directory in reversed(missing):
        directory.mkdir()
        created.append(directory)


def initialize(project: Path, harnesses: list[str]) -> list[Path]:
    """Initialize a Git checkout with unconfigured factory defaults and selected skills."""
    selected = list(dict.fromkeys(harnesses))
    invalid = [name for name in selected if name not in ALL_HARNESSES]
    if invalid:
        raise ValueError(f"unsupported harness selection: {', '.join(invalid)}")
    if not selected:
        raise ValueError("select at least one harness")

    root = _git_root(project)
    factory_state = _target(root, Path(".factory"), allow_directory=True)
    if os.path.lexists(factory_state) and not factory_state.is_dir():
        raise ValueError(".factory exists but is not a directory")

    templates = Path(__file__).resolve().parent / "templates"
    desired = {
        Path("factory.config.json"): (templates / "project-config.json").read_bytes(),
    }
    if "codex" in selected or "opencode" in selected:
        desired[Path(".agents/skills/software-factory/SKILL.md")] = (
            templates / "software-factory/SKILL.md"
        ).read_bytes()
    if "claude" in selected:
        desired[Path(".claude/skills/software-factory/SKILL.md")] = (
            templates / "claude-software-factory/SKILL.md"
        ).read_bytes()

    writes: dict[Path, bytes] = {}
    for relative, content in desired.items():
        path = _target(root, relative)
        if os.path.lexists(path):
            if path.read_bytes() != content and relative != Path("factory.config.json"):
                raise ValueError(f"existing output conflicts with generated content: {relative}")
        else:
            writes[path] = content

    ignore_path = _target(root, Path(".gitignore"))
    ignore_update: tuple[Path, bytes, bytes] | None = None
    if not _ignored(root):
        if ignore_path.is_symlink():
            raise ValueError(".gitignore is a symbolic link and cannot be safely extended")
        original = ignore_path.read_bytes() if os.path.lexists(ignore_path) else b""
        updated = _ignore_with_factory_rule(original)
        if os.path.lexists(ignore_path):
            ignore_update = (ignore_path, original, updated)
        else:
            writes[ignore_path] = updated

    created: list[tuple[Path, tuple[int, int]]] = []
    directories: list[Path] = []
    staged: dict[Path, Path] = {}
    try:
        for destination in [*writes, *(item[0] for item in [ignore_update] if item)]:
            _created_directories(root, destination, directories)
        for destination, content in writes.items():
            staged[destination] = _stage(destination, content)
        if ignore_update:
            path, _, content = ignore_update
            staged[path] = _stage(path, content)

        for destination in writes:
            try:
                # shortcut: atomic no-overwrite promotion needs hard-link support on the target filesystem.
                os.link(staged[destination], destination)
            except FileExistsError as error:
                if not destination.is_file() or destination.read_bytes() != writes[destination]:
                    raise ValueError(f"output changed during initialization: {destination.relative_to(root)}") from error
            else:
                created.append((destination, _identity(destination)))

        if ignore_update:
            path, original, _ = ignore_update
            if path.is_symlink() or path.read_bytes() != original:
                raise ValueError(".gitignore changed during initialization")
            os.chmod(staged[path], stat.S_IMODE(path.stat().st_mode))
            os.replace(staged[path], path)
            result_paths = [*writes, path]
        else:
            result_paths = list(writes)
    except BaseException as error:
        cleanup_errors = _rollback(created)
        cleanup_errors.extend(_cleanup(staged, directories))
        if cleanup_errors:
            details = "; ".join(cleanup_errors)
            raise OSError(f"initialization failed and cleanup was incomplete: {details}") from error
        raise
    cleanup_errors = _cleanup(staged, directories)
    if cleanup_errors:
        raise OSError(f"initialization completed but staging cleanup failed: {'; '.join(cleanup_errors)}")
    return result_paths
