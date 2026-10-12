#!/usr/bin/env bash
# Run from the development .venv without syncing it from PyPI, so the system's PySide6
# stays the one in use (a plain `uv run` or `uv sync` would add PyPI's PySide6 back).
# Builds the environment first (scripts/setup.sh) when it is missing or older than uv.lock. With no command,
# the desktop UI.
#
#   scripts/dev.sh                    myapp
#   scripts/dev.sh -v --db /tmp/t.db  myapp with these options
#   scripts/dev.sh pytest -q          any command: myapp, pytest, ruff, mypy,
#   scripts/dev.sh pre-commit run -a  pre-commit, uv run ... (never syncs)
source "$(dirname -- "${BASH_SOURCE[0]}")/lib.sh"
help_option "$@"

if ! dev_env_ready || outdated "$VENV/pyvenv.cfg" "$ROOT/uv.lock"; then "$ROOT/scripts/setup.sh"; fi
export VIRTUAL_ENV=$VENV
export PATH=$VENV/bin:$PATH
export UV_PROJECT_ENVIRONMENT=$VENV
export UV_NO_SYNC=1  # `uv run` (and the pre-commit hooks) would add PyPI's PySide6 back
cd "$ROOT"
if (( $# == 0 )) || [[ $1 == -* ]]; then
  set -- myapp "$@"
fi
exec "$@"
