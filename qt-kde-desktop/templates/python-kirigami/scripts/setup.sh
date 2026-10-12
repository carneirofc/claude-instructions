#!/usr/bin/env bash
# Build the development environment: .venv on the system Python, seeing the system
# packages, with everything from uv.lock (dev tools included) except PyPI's PySide6, so
# the window uses the system's PySide6 and Kirigami. The system Python gets nothing.
# Run it again after uv.lock changes or the system Python is upgraded.
#
#   scripts/setup.sh                create (or recreate) .venv
#   scripts/setup.sh --deps         the pacman packages it needs, one per line
#   VENV=/path scripts/setup.sh     somewhere else
source "$(dirname -- "${BASH_SOURCE[0]}")/lib.sh"
help_option "$@"
case ${1:-} in
  "") ;;
  --deps) print_packages "${DEPS[@]}"; exit 0 ;;
  *) die "unknown option: $1 (see --help)" 2 ;;
esac

require_packages "${DEPS[@]}"
log "$VENV on $("$SYSTEM_PYTHON" --version), seeing the system packages"
uv venv --quiet --clear --system-site-packages --python "$SYSTEM_PYTHON" "$VENV"
log "uv.lock without PyPI's PySide6"
skip=()
for wheel in "${PYSIDE_WHEELS[@]}"; do skip+=(--no-install-package "$wheel"); done
(cd "$ROOT" && UV_PROJECT_ENVIRONMENT="$VENV" uv sync --frozen --all-extras "${skip[@]}" >&2)
check_pyside "$VENV/bin/python"
log "run it with scripts/dev.sh (the desktop UI), or scripts/dev.sh pytest, ..."
