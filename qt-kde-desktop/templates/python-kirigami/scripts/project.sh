# What myapp needs from the system, for scripts/lib.sh. Only what must match the system's
# Qt comes from pacman (PySide6 and the KDE QML modules Kirigami needs); every other Python
# package comes from uv.lock into a virtual environment, so the system Python gets nothing.
# shellcheck shell=bash

NAME=myapp
APP_ID=io.github.example.myapp
SYSTEM_PYTHON=/usr/bin/python
# The pacman packages setup, dev, build and install need (`scripts/setup.sh --deps`).
DEPS=(git uv gettext 'python>=3.12' pyside6 kirigami kirigami-addons qqc2-desktop-style
  breeze-icons kcoreaddons knotifications qt6-imageformats)
# PyPI's PySide6 (and its parts) is left out: it bundles its own Qt, which cannot load
# the system's Kirigami.
PYSIDE_WHEELS=(pyside6 pyside6-essentials pyside6-addons shiboken6)
# The development environment.
VENV=${VENV:-$ROOT/.venv}

# Fail unless the environment's Python ($1) imports the system's PySide6.
check_pyside() {
  "$1" - <<'PY' >&2
import sys
import PySide6
where = PySide6.__path__[0]
if not where.startswith("/usr/"):
    sys.exit(f"PySide6 comes from {where}, not the system: the window cannot load Kirigami")
print(f"ok: PySide6 {PySide6.__version__} from {where}")
PY
}

# Whether $VENV is the development environment scripts/setup.sh builds.
dev_env_ready() {
  grep -qs "include-system-site-packages = true" "$VENV/pyvenv.cfg" \
    && check_pyside "$VENV/bin/python" 2>/dev/null
}
