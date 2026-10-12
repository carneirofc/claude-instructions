# 13 — Packaging for pacman

## Strategies

| Strategy | When | Reference |
| --- | --- | --- |
| **A. System Python package** — wheel installed with `python -m installer`, every dependency a pacman package | default for Python apps | scraper, template |
| **B. Hybrid** — the Qt UI as a system package; a big backend shipped as a wheel + `uv.lock` pins, installed **per user** as a `uv tool` by a `/usr/bin` bootstrap | the backend needs PyPI-only deps, a specific Python, or browsers | fzonetrack |
| **C. User-local install** (`scripts/install.sh`) — venv in `~/.local/share/<app>/venv` on the system Python with `--system-site-packages`, deps from `uv.lock` minus PySide6 | no root, quick installs, non-Arch | both |
| **D. C++** — `cmake --install` into `$pkgdir` | C++ apps | C++ template |

All of them: PySide6/Kirigami/KF6 **from pacman**.

## Repository layout and the script contract

```
packaging/arch/PKGBUILD  .SRCINFO  <id>.desktop  <id>.metainfo.xml  [python-<dep>/PKGBUILD]
scripts/lib.sh           shared verbatim across repos (fzonetrack, scraper, …)
scripts/project.sh       per repo: NAME, DEPS (pacman), VENV, check_pyside, dev_env_ready
scripts/setup.sh [--deps]                 dev environment; --deps prints pacman packages
scripts/dev.sh [cmd…]                     run from source (UV_NO_SYNC=1)
scripts/build.sh                          wheel/sdist; prints paths
scripts/install.sh [--uninstall]          per-user install (strategy C)
scripts/package.sh [--deps|--srcinfo] [makepkg args…]   build the PKGBUILD from committed HEAD
scripts/i18n.sh                           translations
```

Contract (from `lib.sh`): runs from any directory, idempotent, never prompts unless stdin is
a TTY and `CI` is unset, **logs on stderr, prints only result paths on stdout**; exit 0 ok,
1 failed, 2 bad usage, 3 missing system packages (the message is the `sudo pacman -S
--needed …` to run). That makes the scripts composable from Ansible/CI.

Key `lib.sh` helpers: `require_packages` (`pacman -T` → exit 3 with the install command),
`require_command`, `outdated target sources…`, `interactive`, `pkgbuild_packages` (sources
the PKGBUILD in a subshell → keep it side-effect free), `package_arch`:

```bash
local stage=${ARCH_BUILD_DIR:-${XDG_CACHE_HOME:-$HOME/.cache}/arch-build/${ROOT##*/}}
local source=${PKG_SOURCE-file://$ROOT}           # '-' not ':-': PKG_SOURCE= means upstream
[[ -n $(git -C "$ROOT" status --porcelain) ]] && warn "uncommitted changes are not packaged"
git -C "$ROOT" ls-files -z --cached --others --exclude-standard -- packaging/arch |
  (cd "$ROOT" && tar --null --files-from=- -cf -) | tar -C "$stage" --strip-components=2 -xf -
(cd "$stage" && PKG_SOURCE=$source makepkg "${flags[@]}" "$@" >&2) || status=$?
case $status in 0) ;; 13) log "already built" ;; *) die "makepkg failed (exit $status)" ;; esac
(cd "$stage" && PKG_SOURCE=$source makepkg --packagelist)   # → stdout
```

The checkout stays clean (makepkg works in `~/.cache/arch-build/<repo>`), only the
**committed HEAD** is built (the PKGBUILD clones `$PKG_SOURCE`), and exit 13 ("already
built") is success.

## PKGBUILD — Python (strategy A)

Full file: [`templates/python-kirigami/packaging/arch/PKGBUILD`](templates/python-kirigami/packaging/arch/PKGBUILD)
(built and checked end-to-end with makepkg while writing this guide).

```bash
pkgname=myapp-git
arch=('any')
depends=(
  'python' 'python-pillow' 'python-platformdirs'          # pyproject deps → Arch names
  'pyside6' 'qt6-declarative' 'kirigami' 'kirigami-addons' 'qqc2-desktop-style'
  'breeze-icons' 'hicolor-icon-theme' 'qt6-svg' 'qt6-imageformats' 'qt6-wayland'
  'kcoreaddons' 'knotifications'                          # + their Python bindings
)
optdepends=('plasma-integration: Plasma colours, fonts, icons and file dialogs, also outside Plasma')
makedepends=('git' 'gettext' 'python-build' 'python-installer' 'python-hatchling' 'python-wheel')
checkdepends=('python-pytest' 'python-pytest-qt' 'desktop-file-utils' 'appstream')
provides=("$_name"); conflicts=("$_name")
source=("$_name::git+${PKG_SOURCE:-https://example.org/myapp.git}"); sha256sums=('SKIP')

build() {
  cd "$_name"
  python -m build --wheel --no-isolation                  # offline, system backend
  scripts/i18n.sh compile "$srcdir/locale" >/dev/null
}
check() {
  cd "$_name"
  desktop-file-validate "packaging/arch/$_id.desktop"
  appstreamcli validate --no-net "packaging/arch/$_id.metainfo.xml"
  listing=$(python -m zipfile -l dist/*.whl)
  grep -q "$_name/qml/Main.qml" <<<"$listing"               # the wheel carries the QML
  site=$(python -c 'import site; print(site.getsitepackages()[0])')
  python -m installer --destdir="$srcdir/test-env" dist/*.whl
  QT_QPA_PLATFORM=offscreen PYTHONPATH="$srcdir/test-env$site" python -m pytest -q -p no:cacheprovider tests
}
package() {
  cd "$_name"
  python -m installer --destdir="$pkgdir" dist/*.whl      # site-packages + /usr/bin/myapp
  install -Dm644 "packaging/arch/$_id.desktop" -t "$pkgdir/usr/share/applications"
  install -Dm644 "packaging/arch/$_id.metainfo.xml" -t "$pkgdir/usr/share/metainfo"
  install -Dm644 "src/$_name/data/icons/$_id.svg" -t "$pkgdir/usr/share/icons/hicolor/scalable/apps"
  install -Dm644 "src/$_name/data/knotifications6/$_name.notifyrc" -t "$pkgdir/usr/share/knotifications6"
  cp -r "$srcdir/locale" "$pkgdir/usr/share/"
  install -Dm644 LICENSE -t "$pkgdir/usr/share/licenses/$pkgname"
}
```

**Dependency mapping**: pyproject name → Arch name, checked with
`pacman -Ss '^python-<name>$'`. Watch for spelling differences — scraper's
`python-curl-cffi` made the package uninstallable; Arch calls it `python-curl_cffi`.
Extras become `optdepends` ("(AUR)" when they are). The build backend goes in
`makedepends` (`python-hatchling`, `python-uv-build`, `python-setuptools`…) so
`--no-isolation` works offline. Alternatively `uv build --wheel` (fzonetrack) — then set
`UV_CACHE_DIR="$srcdir/uv-cache"` to keep uv out of the builder's `$HOME`.

**`check()` earns its keep**: fzonetrack's first check looked for `webui/index.html` at the
wheel root (it lives under the package) and failed every build; scraper's first check
imported from the bare clone (no `src/` on the path, no metadata) — install the wheel into a
scratch prefix and test that instead.

## PKGBUILD — C++ (strategy D)

```bash
arch=('x86_64')
depends=('qt6-base' 'qt6-declarative' 'kirigami' 'kirigami-addons' 'qqc2-desktop-style'
         'kcoreaddons' 'ki18n' 'kconfig' 'kiconthemes' 'knotifications' 'kdbusaddons' 'kio' …)
makedepends=('git' 'cmake' 'ninja' 'extra-cmake-modules' 'qt6-tools')
build()   { cmake -B build -S "$_name" -G Ninja -DCMAKE_BUILD_TYPE=None -DCMAKE_INSTALL_PREFIX=/usr -DBUILD_TESTING=OFF; cmake --build build; }
package() { DESTDIR="$pkgdir" cmake --install build; }
```

`CMAKE_BUILD_TYPE=None` lets makepkg's `CFLAGS`/`CXXFLAGS` apply. Run `namcap` on the built
package: it reports missing/unneeded link dependencies.

## Dependencies missing from the repos

Prefer, in order: the official repos → a **companion PKGBUILD in your repo**
(`packaging/arch/python-<name>/PKGBUILD`, pinned to the `uv.lock` version, PyPI sdist with a
real sha256, built against the system Python; `package.sh` builds and installs it first when
`pacman -T` says it's missing — scraper's `python-selectolax`) → the AUR → strategy B.
Compiled extensions are `arch=('x86_64')`; run their tests against the installed wheel from
outside the source tree.

## Versioning

```bash
pkgver() {
  cd "$_name"
  if described=$(git describe --tags --long --match 'v[0-9]*' --abbrev=7 2>/dev/null); then
    printf '%s' "$described" | sed 's/^v//;s/\([^-]*-\)g/r\1g/;s/-/./g'   # v1.0.1-468-g930fb94 → 1.0.1.r468.g930fb94
  else
    printf '%s.r%s.g%s' "$(grep -Po '^version = "\K[^"]+' pyproject.toml)" \
      "$(git rev-list --count HEAD)" "$(git rev-parse --short=7 HEAD)"
  fi
}
```

- `--match 'v[0-9]*'` so a moving `nightly` tag never becomes a version (fzonetrack).
- The committed `pkgver=` is only a seed; makepkg rewrites it in the staged copy.
- SemVer tags `vX.Y.Z`; the pyproject/CMake version is the base between tags.
- **Regenerate `.SRCINFO`** whenever the PKGBUILD changes (`scripts/package.sh --srcinfo`) —
  both reference repos had drifted `.SRCINFO` files.

## `.install` scriptlets

Pacman hooks already run `gtk-update-icon-cache`, `update-desktop-database`,
`update-mime-database` and the AppStream cache update when files land in those dirs (present
in `/usr/share/libalpm/hooks/`). Don't repeat them. Use `.install` only for **messages** a
system package can't act on: per-user steps, what upgrade requires
(`systemctl --user try-restart <app>`), what removal leaves behind (fzonetrack).

## Strategy B details (fzonetrack)

- The package ships `/usr/share/<app>/<wheel>`, `<app>-constraints.txt` (from `uv export
  --frozen --no-dev --no-hashes --no-emit-project`, header stripped because it embeds the
  build path), a JSON **marker** naming the wheel, and `/usr/bin/<app>` = bootstrap.
- The bootstrap (POSIX sh): if the marker differs from the copy in the user's uv tool env
  (or the tool's interpreter is dangling) → take a `flock` in `$XDG_RUNTIME_DIR`, re-check,
  `uv tool install --force --python 3.14 --constraints … <wheel>`, copy the marker; then
  `exec` the real entry point. Under systemd (`INVOCATION_ID` set) it avoids restarting its
  own unit.
- The app refuses self-update when the marker exists ("rebuild the package instead"), and
  the standalone installer refuses while the package is installed — the two install paths
  never fight.

## End-to-end

```sh
sudo pacman -S --needed $(scripts/setup.sh --deps)
uv lock && scripts/setup.sh              # dev env (system PySide6)
scripts/dev.sh                           # run; scripts/dev.sh pytest -q
git commit …                             # makepkg builds HEAD only
scripts/package.sh --srcinfo             # after PKGBUILD edits; commit .SRCINFO
scripts/package.sh -si                   # build + install (deps via -s)
sudo pacman -R myapp-git                 # remove; user data stays
scripts/install.sh / --uninstall         # strategy C instead of a package
```

## CI

Neither reference repo builds its package in CI. A minimal gate (template — not run here):

```yaml
jobs:
  arch:
    runs-on: ubuntu-latest
    container: archlinux:latest
    steps:
      - run: pacman -Syu --noconfirm --needed base-devel git namcap shellcheck
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - run: shellcheck scripts/*.sh packaging/arch/PKGBUILD -e SC2034,SC2154,SC2164
      - run: |
          useradd -m builder && chown -R builder .
          su builder -c 'cd packaging/arch && makepkg --printsrcinfo | diff - .SRCINFO'
          pacman -S --noconfirm --needed $(su builder -c 'scripts/package.sh --deps')
          su builder -c 'PKG_SOURCE=file://$PWD CI=1 scripts/package.sh'
          namcap ~builder/.cache/arch-build/*/*.pkg.tar.zst
```

On Ubuntu runners (no Kirigami) keep the pure-Python and non-QML tests, with
`QT_QPA_PLATFORM=offscreen` and the Qt runtime libs (`libegl1 libgl1 libxkbcommon0
libfontconfig1 libdbus-1-3`) — scraper's CI does this; QML tests then skip via the
Kirigami probe fixture.
