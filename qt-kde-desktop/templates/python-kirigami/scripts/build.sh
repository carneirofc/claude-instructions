#!/usr/bin/env bash
# Build the sdist and the wheel into dist/ and print their paths.
#
#   scripts/build.sh                  uv build (extra arguments go to it)
source "$(dirname -- "${BASH_SOURCE[0]}")/lib.sh"
help_option "$@"

require_command uv
rm -rf "$ROOT/dist"
(cd "$ROOT" && uv build --quiet "$@" >&2)
print_existing "$ROOT"/dist/*
