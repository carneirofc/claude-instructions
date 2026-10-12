#!/usr/bin/env bash
# Build the Arch package from packaging/arch/PKGBUILD and print the packages' paths.
# makepkg works on a copy of packaging/arch in ~/.cache/arch-build/<repository> and
# clones this checkout's committed HEAD; the checkout itself is left untouched.
# A dependency the repositories lack is built from its recipe in packaging/arch/<name>/
# and installed first, when it is not installed already (list them in LOCAL_RECIPES).
#
#   scripts/package.sh               build (an unchanged commit is not built again)
#   scripts/package.sh -si           also install missing dependencies, then the package
#   scripts/package.sh -f            build again
#   scripts/package.sh --deps        the PKGBUILD's dependencies of every kind, one per line
#   scripts/package.sh --srcinfo     regenerate packaging/arch/.SRCINFO (commit it)
#   PKG_SOURCE= scripts/package.sh   build the PKGBUILD's own default source instead
#   ARCH_BUILD_DIR=DIR               where makepkg works
source "$(dirname -- "${BASH_SOURCE[0]}")/lib.sh"
help_option "$@"
case ${1:-} in
  --deps) pkgbuild_packages; exit 0 ;;
  --srcinfo)
    (cd "$ARCH_RECIPE" && makepkg --printsrcinfo >.SRCINFO)
    printf '%s\n' "$ARCH_RECIPE/.SRCINFO"
    exit 0
    ;;
esac

# Dependencies the repositories lack, as their recipe's directory in this repository,
# e.g. LOCAL_RECIPES=(packaging/arch/python-foo).
LOCAL_RECIPES=()

local_dependencies() {
  local recipe name cache status
  local flags=(--noprogressbar --syncdeps --install --needed)
  interactive || flags+=(--noconfirm)
  for recipe in "${LOCAL_RECIPES[@]}"; do
    name=${recipe##*/}
    pacman -T "$name" >/dev/null && continue
    cache=${XDG_CACHE_HOME:-$HOME/.cache}/arch-build/$name
    log "$name is not in the repositories: building $recipe"
    mkdir -p "$cache/build" "$cache/sources"
    status=0
    (cd "$ROOT/$recipe" &&
      BUILDDIR=$cache/build SRCDEST=$cache/sources PKGDEST=$cache makepkg "${flags[@]}" >&2) ||
      status=$?
    [[ $status == 0 ]] || die "makepkg failed for $name (exit $status)"
  done
}

local_dependencies
package_arch "$@"
