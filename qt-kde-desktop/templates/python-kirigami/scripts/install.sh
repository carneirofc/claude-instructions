#!/usr/bin/env bash
# Install myapp for this user, without sudo and without touching the system Python: a
# private environment in ~/.local/share/myapp/venv (the system Python, seeing the system
# packages, plus the versions uv.lock pins, minus PyPI's PySide6), the command linked into
# ~/.local/bin, the launcher, icon, notification events and translations in ~/.local/share.
# Run it again to update. Prefer scripts/package.sh -si when a pacman package is wanted.
#
#   scripts/install.sh              install or update
#   scripts/install.sh --uninstall  remove it (your data in ~/.local/share/myapp stays)
source "$(dirname -- "${BASH_SOURCE[0]}")/lib.sh"
data=${XDG_DATA_HOME:-$HOME/.local/share}
bin=${XDG_BIN_HOME:-$HOME/.local/bin}
venv=$data/$NAME/venv
commands=(myapp)
files=("$data/applications/$APP_ID.desktop" "$data/icons/hicolor/scalable/apps/$APP_ID.svg"
  "$data/knotifications6/$NAME.notifyrc")

uninstall() {
  local command
  for command in "${commands[@]}"; do
    [[ $(readlink "$bin/$command" 2>/dev/null) == "$venv/"* ]] && rm "$bin/$command"
  done
  rm -rf "$venv" "${files[@]}"
  find "$data/locale" -path "*/LC_MESSAGES/$NAME.mo" -delete 2>/dev/null || true
  log "removed $NAME (its data in $data/$NAME is kept)"
}

case ${1:-} in
  "") ;;
  --uninstall) uninstall; exit 0 ;;
  -h|--help) usage; exit 0 ;;
  *) die "unknown option: $1 (see --help)" 2 ;;
esac

require_packages "${DEPS[@]}"
log "$venv on $("$SYSTEM_PYTHON" --version)"
uv venv --quiet --clear --system-site-packages --python "$SYSTEM_PYTHON" "$venv"
requirements=$(mktemp)
trap 'rm -f "$requirements"' EXIT
(cd "$ROOT" && uv export --quiet --frozen --no-dev --no-emit-project --prune pyside6 \
  --output-file "$requirements" >&2)
uv pip install --quiet --python "$venv/bin/python" --requirement "$requirements"
uv pip install --quiet --python "$venv/bin/python" --no-deps "$ROOT"
check_pyside "$venv/bin/python"

mkdir -p "$bin"
for command in "${commands[@]}"; do ln -sf "$venv/bin/$command" "$bin/$command"; done
install -Dm644 "$ROOT/src/$NAME/data/icons/$APP_ID.svg" "${files[1]}"
install -Dm644 "$ROOT/src/$NAME/data/knotifications6/$NAME.notifyrc" "${files[2]}"
sed -e "s|^Exec=myapp|Exec=$venv/bin/myapp|" -e "s|^TryExec=.*|TryExec=$venv/bin/myapp|" \
  "$ROOT/packaging/arch/$APP_ID.desktop" | install -Dm644 /dev/stdin "${files[0]}"
"$ROOT/scripts/i18n.sh" compile "$data/locale" >/dev/null
# No pacman hook watches ~/.local: refresh the menu's cache ourselves.
command -v update-desktop-database >/dev/null && update-desktop-database "$data/applications" || true
case ":$PATH:" in *":$bin:"*) ;; *) warn "$bin is not on PATH" ;; esac
echo "$venv"
