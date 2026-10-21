#!/usr/bin/env python3
"""Safely merge software factory scaffold into an existing repository."""
from pathlib import Path
import argparse
import shutil
import subprocess
import sys

HOME = Path(__file__).resolve().parent
SPECIAL = {"AGENTS.md", "CLAUDE.md", ".gitignore"}
SKIP = {"install.py", "__pycache__"}
INSTALL_TOP = {"factory.py", "skillctl.py", "factory.config.json", "POLICY.md", "AGENTS.md", "CLAUDE.md", ".gitignore", "FACTORY_SETUP.md"}
INSTALL_DIRS = {"roles", ".claude", ".agents", "examples", "specs", "skills"}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("repo", type=Path, help="Existing Git repository path")
    args = p.parse_args()
    repo = args.repo.resolve()
    if not (repo / ".git").exists():
        print("ERROR: target must be an existing Git checkout", file=sys.stderr)
        return 2
    srcs = [f for f in HOME.rglob("*") if f.is_file() and (str(f.relative_to(HOME)) in INSTALL_TOP or f.relative_to(HOME).parts[0] in INSTALL_DIRS) and not any(x in SKIP for x in f.relative_to(HOME).parts) and f.suffix != '.pyc']
    clashes = [str(f.relative_to(HOME)) for f in srcs if str(f.relative_to(HOME)) not in SPECIAL and (repo / f.relative_to(HOME)).exists()]
    if clashes:
        print("ERROR: refusing to overwrite existing files:\n" + "\n".join(clashes), file=sys.stderr)
        return 2
    for f in srcs:
        rel = f.relative_to(HOME)
        dest = repo / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if str(rel) in SPECIAL and dest.exists():
            addition = f.read_text(encoding='utf-8')
            prior = dest.read_text(encoding='utf-8')
            marker = '# Software Factory Instructions' if rel.name != '.gitignore' else '# Software Factory ignored outputs'
            if marker not in prior:
                dest.write_text(prior.rstrip() + '\n\n' + marker + '\n' + addition.rstrip() + '\n', encoding='utf-8')
        else:
            shutil.copy2(f, dest)
    print(f"Installed {len(srcs)} scaffold files into {repo}. Configure factory.config.json and commit the files before running.")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
