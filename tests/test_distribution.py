from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.6.0"


def run(
    command: list[str], *, cwd: Path, extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    clean_env = os.environ.copy()
    clean_env.pop("PYTHONPATH", None)
    clean_env["PYTHONUTF8"] = "1"
    clean_env["PYTHONDONTWRITEBYTECODE"] = "1"
    if extra_env:
        clean_env.update(extra_env)
    return subprocess.run(command, cwd=cwd, env=clean_env, text=True, capture_output=True)


class DistributionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.uv = shutil.which("uv")
        if not cls.uv:
            raise RuntimeError("uv is required for distribution tests")
        cls.temp = tempfile.TemporaryDirectory(prefix="factory-dist-")
        cls.addClassCleanup(cls.temp.cleanup)
        cls.temp_path = Path(cls.temp.name)
        cls.artifacts = cls.temp_path / "artifacts"
        cls.artifacts.mkdir()
        result = run([cls.uv, "build", "--out-dir", str(cls.artifacts)], cwd=ROOT)
        if result.returncode:
            raise RuntimeError(f"uv build failed ({result.returncode}):\n{result.stdout}\n{result.stderr}")
        wheels = list(cls.artifacts.glob("*.whl"))
        sdists = list(cls.artifacts.glob("*.tar.gz"))
        if len(wheels) != 1 or len(sdists) != 1:
            raise AssertionError(f"expected one wheel and sdist, found {wheels!r}, {sdists!r}")
        cls.wheel = wheels[0]
        cls.sdist = sdists[0]

    def install(self, wheel: Path, name: str) -> tuple[Path, Path]:
        environment = self.temp_path / name
        result = run([self.uv, "venv", "--python", sys.executable, str(environment)], cwd=self.temp_path)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        result = run([self.uv, "pip", "install", "--python", str(python), str(wheel)], cwd=self.temp_path)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        script = environment / ("Scripts/software-factory.exe" if os.name == "nt" else "bin/software-factory")
        return python, script

    def exercise_installed_cli_project(self, script: Path, name: str) -> None:
        project = self.temp_path / f"{name} consumer workspace 雪"
        project.mkdir()
        outside = self.temp_path / f"{name} foreign directory"
        outside.mkdir()
        stub_dir = self.temp_path / f"{name} host bin"
        stub_dir.mkdir()
        stub_marker = self.temp_path / f"{name}-codex-stub-invoked"
        if os.name == "nt":
            stub = stub_dir / "codex.cmd"
            stub.write_text(
                '@echo off\r\necho invoked> "%CODEX_STUB_MARKER%"\r\nexit /b 0\r\n',
                encoding="utf-8",
            )
        else:
            stub = stub_dir / "codex"
            stub.write_text(
                '#!/bin/sh\n: > "$CODEX_STUB_MARKER"\nexit 0\n', encoding="utf-8",
            )
            stub.chmod(0o755)
        stub_env = {
            "PATH": str(stub_dir) + os.pathsep + os.environ.get("PATH", ""),
            "CODEX_STUB_MARKER": str(stub_marker),
        }

        result = run(["git", "init", "--quiet"], cwd=project)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

        initialized = run(
            [str(script), "init", "--project", str(project), "--harness", "codex"],
            cwd=outside,
        )
        self.assertEqual(initialized.returncode, 0, initialized.stdout + initialized.stderr)
        self.assertTrue((project / ".agents/skills/software-factory/SKILL.md").is_file())
        self.assertFalse((project / "factory.py").exists())
        self.assertFalse((project / "dashboard.py").exists())

        unready = run(
            [str(script), "doctor", "--project", str(project)], cwd=outside, extra_env=stub_env,
        )
        self.assertEqual(unready.returncode, 2, unready.stdout + unready.stderr)
        self.assertIn("gate", (unready.stdout + unready.stderr).lower())
        empty_status = run([str(script), "status", "--project", str(project)], cwd=outside)
        self.assertEqual(empty_status.returncode, 0, empty_status.stdout + empty_status.stderr)
        self.assertIn("no run", (empty_status.stdout + empty_status.stderr).lower())

        config_path = project / "factory.config.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        self.assertEqual(config["required_gates"], ["tests", "lint", "security", "build"])
        ruff = shutil.which("ruff")
        if not ruff:
            self.fail("Ruff must be installed from requirements-dev.txt for this artifact fixture")
        config["commands"]["tests"] = [[sys.executable, "-m", "unittest", "discover", "-s", "tests"]]
        config["commands"]["lint"] = [[ruff, "check", "--no-cache", "tests"]]
        config["commands"]["security"] = [[ruff, "check", "--no-cache", "--select", "S", "tests"]]
        config["commands"]["build"] = [[sys.executable, "-m", "compileall", "-q", "tests"]]
        config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
        tests_dir = project / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_consumer_contract.py").write_text(
            "import json\n"
            "import unittest\n"
            "from pathlib import Path\n\n\n"
            "class ConsumerInitializationTests(unittest.TestCase):\n"
            "    def test_codex_defaults_without_factory_source(self):\n"
            "        config = json.loads(Path('factory.config.json').read_text(encoding='utf-8'))\n"
            "        roles = ('planner', 'build_orchestrator', 'builder', 'testing', "
            "'architecture', 'ui', 'ux', 'security')\n"
            "        self.assertEqual(config['providers'], {role: 'codex' for role in roles})\n"
            "        self.assertEqual(config['models']['planner'], 'gpt-6-sol')\n"
            "        self.assertEqual(config['models']['builder'], 'gpt-6-luna')\n"
            "        self.assertTrue(Path('.agents/skills/software-factory/SKILL.md').is_file())\n"
            "        self.assertFalse(Path('factory.py').exists())\n"
            "        self.assertFalse(Path('dashboard.py').exists())\n",
            encoding="utf-8",
        )
        for command in (
            ["git", "-c", "user.name=Factory Test", "-c", "user.email=factory@example.test", "add", "-A"],
            ["git", "-c", "user.name=Factory Test", "-c", "user.email=factory@example.test",
             "commit", "--quiet", "-m", "Initial consumer fixture"],
        ):
            result = run(command, cwd=project)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

        for gate, commands in config["commands"].items():
            for command in commands:
                gate_env = None
                if gate == "build":
                    gate_env = {"PYTHONPYCACHEPREFIX": str(self.temp_path / f"{name}-pycache")}
                result = run(command, cwd=project, extra_env=gate_env)
                self.assertEqual(result.returncode, 0, f"{gate}: {result.stdout}{result.stderr}")

        ready = run(
            [str(script), "doctor", "--project", str(project)], cwd=outside, extra_env=stub_env,
        )
        self.assertEqual(ready.returncode, 0, ready.stdout + ready.stderr)
        dry_run = run(
            [str(script), "run", "--idea", "artifact smoke request", "--project", str(project), "--dry-run"],
            cwd=outside,
            extra_env=stub_env,
        )
        self.assertEqual(dry_run.returncode, 0, dry_run.stdout + dry_run.stderr)
        self.assertIn("DRY RUN", dry_run.stdout)
        run_dirs = list((project / ".factory" / "runs").glob("*"))
        self.assertEqual(len(run_dirs), 1)
        self.assertTrue((run_dirs[0] / "dry-run.json").is_file())

        after_run = run([str(script), "status", "--project", str(project)], cwd=outside)
        self.assertEqual(after_run.returncode, 0, after_run.stdout + after_run.stderr)
        state = (after_run.stdout + after_run.stderr).lower()
        self.assertTrue(any(value in state for value in ("preflight", "dry_run", "dry run")), state)
        self.assertFalse(stub_marker.exists(), "doctor or dry-run executed the Codex placeholder")
        dirty = run(["git", "status", "--porcelain"], cwd=project)
        self.assertEqual(dirty.returncode, 0, dirty.stdout + dirty.stderr)
        self.assertEqual(dirty.stdout, "")

    def test_source_version_fallback(self) -> None:
        outside = Path(tempfile.mkdtemp(prefix="factory-source-cli-"))
        try:
            result = run([sys.executable, str(ROOT / "cli.py"), "--version"], cwd=outside)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(result.stdout.strip(), VERSION)
        finally:
            shutil.rmtree(outside)

    def test_wheel_runs_outside_source_tree(self) -> None:
        _, script = self.install(self.wheel, "wheel-venv")
        outside = self.temp_path / "foreign-working-directory"
        outside.mkdir()
        help_result = run([str(script), "--help"], cwd=outside)
        self.assertEqual(help_result.returncode, 0, help_result.stdout + help_result.stderr)
        self.assertIn("usage:", help_result.stdout.lower())
        version_result = run([str(script), "--version"], cwd=outside)
        self.assertEqual(version_result.returncode, 0, version_result.stdout + version_result.stderr)
        self.assertEqual(version_result.stdout.strip(), VERSION)
        self.exercise_installed_cli_project(script, "wheel")

    def test_sdist_builds_self_contained_wheel(self) -> None:
        extracted = self.temp_path / "sdist-source"
        extracted.mkdir()
        with tarfile.open(self.sdist, "r:gz") as archive:
            members = archive.getnames()
            self.assertFalse(any("/.factory/" in "/" + name for name in members))
            self.assertFalse(any("node_modules" in Path(name).parts for name in members))
            self.assertFalse(any("skills/lock.json" in name.replace("\\\\", "/") for name in members))
            self.assertFalse(any(name.endswith("/factory.config.json") for name in members))
            archive.extractall(extracted)
        source = next(path for path in extracted.iterdir() if path.is_dir())
        wheelhouse = self.temp_path / "sdist-wheel"
        wheelhouse.mkdir()
        result = run([self.uv, "build", "--wheel", "--out-dir", str(wheelhouse)], cwd=source)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        wheels = list(wheelhouse.glob("*.whl"))
        self.assertEqual(len(wheels), 1)
        _, script = self.install(wheels[0], "sdist-venv")
        outside = self.temp_path / "sdist-foreign-directory"
        outside.mkdir()
        result = run([str(script), "--help"], cwd=outside)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.exercise_installed_cli_project(script, "sdist-wheel")

    def test_packaged_supervisor_main_uses_namespaced_checkout_import(self) -> None:
        python, _ = self.install(self.wheel, "supervisor-venv")
        project = self.temp_path / "not-a-git-project"
        project.mkdir()
        outside = self.temp_path / "supervisor-foreign-directory"
        outside.mkdir()
        code = (
            "import sys; from codex_software_factory.factory import main; "
            "sys.argv = ['software-factory', '--idea', 'smoke', '--project', sys.argv[1]]; "
            "raise SystemExit(main())"
        )
        result = run([str(python), "-c", code, str(project)], cwd=outside)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("BLOCKED: Project must be a Git checkout", result.stderr)

    def test_install_has_no_generic_top_level_modules(self) -> None:
        with zipfile.ZipFile(self.wheel) as archive:
            names = set(archive.namelist())
        roots = {name.split("/", 1)[0] for name in names if "/" in name}
        self.assertEqual(roots, {"codex_software_factory", "codex_software_factory-0.6.0.dist-info"})
        self.assertFalse(any(name.endswith("/skills/lock.json") for name in names))
        self.assertFalse(any(name.endswith("/factory.config.json") for name in names))
        for resource in (
            "codex_software_factory/POLICY.md",
            "codex_software_factory/LICENSE",
            "codex_software_factory/roles/builder.md",
            "codex_software_factory/skills/registry.json",
            "codex_software_factory/app/server.py",
        ):
            self.assertIn(resource, names)

        python, _ = self.install(self.wheel, "namespaced-venv")
        outside = self.temp_path / "namespaced-foreign-directory"
        outside.mkdir()
        result = run(
            [
                str(python),
                "-c",
                "import importlib.util; assert importlib.util.find_spec('app') is None; "
                "assert importlib.util.find_spec('factory') is None; "
                "import codex_software_factory.factory",
            ],
            cwd=outside,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_help_without_optional_dependencies(self) -> None:
        python, script = self.install(self.wheel, "minimal-venv")
        outside = self.temp_path / "minimal-foreign-directory"
        outside.mkdir()
        result = run(
            [
                str(python),
                "-c",
                "import importlib.util; assert importlib.util.find_spec('fastapi') is None; "
                "assert importlib.util.find_spec('uvicorn') is None",
            ],
            cwd=outside,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        result = run([str(script), "--help"], cwd=outside)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        result = run([str(script), "--version"], cwd=outside)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.strip(), VERSION)


if __name__ == "__main__":
    unittest.main()
