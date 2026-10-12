#!/usr/bin/env bash
# Translations with gettext, the KDE way: po/<lang>.po per language, one myapp.pot template.
#
#   scripts/i18n.sh extract          refresh po/myapp.pot from the Python and QML sources
#   scripts/i18n.sh update           extract, then merge the template into every po/*.po
#   scripts/i18n.sh new pt_BR        start po/pt_BR.po
#   scripts/i18n.sh compile [DIR]    po/*.po -> DIR/<lang>/LC_MESSAGES/myapp.mo
#                                    (default: src/myapp/locale, which the app finds in dev)
source "$(dirname -- "${BASH_SOURCE[0]}")/lib.sh"
help_option "$@"
require_command xgettext gettext

DOMAIN=myapp
PO=$ROOT/po
POT=$PO/$DOMAIN.pot
# The functions that mark strings, with the argument holding the context (c) and plurals.
KEYWORDS=(-ki18n:1 -ki18nc:1c,2 -ki18np:1,2 -ki18ncp:1c,2,3 -ktr:1 -ktrp:1,2)
COMMON=(--from-code=UTF-8 --add-comments=TRANSLATORS: --package-name="$DOMAIN" --sort-by-file
  --no-wrap "${KEYWORDS[@]}")

extract() {
  mkdir -p "$PO"
  local tmp_py tmp_qml
  tmp_py=$(mktemp) tmp_qml=$(mktemp)
  trap 'rm -f "$tmp_py" "$tmp_qml"' RETURN
  (cd "$ROOT" && git ls-files --cached --others --exclude-standard 'src/*.py' 2>/dev/null ||
    find src -name '*.py') | sort >"$tmp_py"
  (cd "$ROOT" && git ls-files --cached --others --exclude-standard 'src/*.qml' 2>/dev/null ||
    find src -name '*.qml') | sort >"$tmp_qml"
  # QML parses well enough as JavaScript for string extraction.
  (cd "$ROOT" &&
    xgettext "${COMMON[@]}" --language=Python -f "$tmp_py" -o "$POT" &&
    xgettext "${COMMON[@]}" --language=JavaScript -f "$tmp_qml" -j -o "$POT")
  log "$(grep -c '^msgid ' "$POT") strings in ${POT#"$ROOT"/}"
}

update() {
  extract
  local po
  for po in "$PO"/*.po; do
    [[ -e $po ]] || continue
    msgmerge --quiet --update --backup=none --no-wrap "$po" "$POT"
    log "$(basename "$po"): $(msgfmt --statistics -o /dev/null "$po" 2>&1)"
  done
}

compile() {
  local out=${1:-$ROOT/src/$DOMAIN/locale} po lang
  for po in "$PO"/*.po; do
    [[ -e $po ]] || continue
    lang=$(basename "$po" .po)
    mkdir -p "$out/$lang/LC_MESSAGES"
    msgfmt --check -o "$out/$lang/LC_MESSAGES/$DOMAIN.mo" "$po"
    printf '%s\n' "$out/$lang/LC_MESSAGES/$DOMAIN.mo"
  done
}

case ${1:-} in
  extract) extract ;;
  update) update ;;
  new)
    [[ -n ${2:-} ]] || die "usage: scripts/i18n.sh new LANG" 2
    [[ -e $POT ]] || extract
    msginit --no-translator --no-wrap --locale="$2" -i "$POT" -o "$PO/$2.po"
    ;;
  compile) compile "${2:-}" ;;
  *) die "unknown command: ${1:-} (see --help)" 2 ;;
esac
