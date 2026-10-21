#!/usr/bin/env sh
set -eu
project_root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
python_bin="$project_root/.venv/bin/python"
if [ ! -x "$python_bin" ]; then
    python_bin="$project_root/.factory/venv/bin/python"
fi
if [ ! -x "$python_bin" ]; then
    python_bin=python3
fi
exec "$python_bin" "$project_root/dashboard.py" "$@"
