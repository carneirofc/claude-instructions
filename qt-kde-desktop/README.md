# KDE-native Qt/QML desktop apps — Python & C++, packaged for pacman

A reference for building desktop apps that look and behave like they belong on the user's
KDE Plasma (or any Qt) desktop: native controls, the user's colours/fonts/icons/animation
speed ("ricing" respected), responsive layouts, motion, icons, feedback, i18n, async work,
caching, file handling — and shipping them as Arch packages.

Distilled from two working apps — **fzonetrack** (`qtui/`, PySide6 + Kirigami, REST/SSE
client, tray, KNotifications) and **scraper** (`src/scraper/qt/`, PySide6 + Kirigami,
asyncio worker, image provider, keyboard-first lists) — plus KDE/Qt documentation, with
every API checked against Qt 6.11 / KF 6.30 / Kirigami 6.30 as installed on Arch
(2026-10).

## Start here

| You want to… | Read |
| --- | --- |
| Start a new app fast | Copy [`templates/python-kirigami`](templates/python-kirigami) (runnable, tested, packaged) or [`templates/cpp-kirigami`](templates/cpp-kirigami) |
| Understand the layering and the rules | [01 Architecture](01-architecture.md) |
| Get the native look and respect the user's theme | [02 Native look & ricing](02-native-look-and-ricing.md) |
| Python specifics (PySide6, missing KDE bindings) | [03 Python / PySide6](03-python-pyside6.md) |
| C++ specifics (CMake/ECM, KF6) | [04 C++ / KF6](04-cpp-kf6.md) |
| Pages, responsive layout, forms, keyboard, dialogs | [05 QML & Kirigami UI](05-qml-kirigami-ui.md) |
| Motion | [06 Animation](06-animation.md) |
| Icons, images, thumbnails, WebP | [07 Icons & images](07-icons-and-images.md) |
| Toasts, inline messages, progress, notifications | [08 User feedback](08-user-feedback.md) |
| Background work, external commands, files & folders | [09 Async, commands, files](09-async-commands-files.md) |
| Translations | [10 Internationalisation](10-i18n.md) |
| Settings, state, cache, database | [11 Storage & cache](11-storage-and-cache.md) |
| Desktop file, AppStream, D-Bus, tray, Wayland app id | [12 Desktop integration](12-desktop-integration.md) |
| PKGBUILD, scripts, versioning | [13 Packaging for pacman](13-packaging-pacman.md) |
| Headless tests, qmllint, CI | [14 Testing & tooling](14-testing-and-tooling.md) |

## The rules (non-negotiable)

1. **The app owns layout and behaviour; the user's desktop owns the look.** QML never
   contains a hex colour, a pixel size or a millisecond literal: only `Kirigami.Theme.*`,
   `Kirigami.Units.*` and theme icon names. ([02](02-native-look-and-ricing.md))
2. **`QApplication` + the `org.kde.desktop` style**, set only when the user has not chosen
   one (`QT_QUICK_CONTROLS_STYLE`). Breeze is the *fallback* icon theme, never forced.
3. **One reverse-DNS app id everywhere** — `.desktop` name, icon name, AppStream id, D-Bus
   name, `setDesktopFileName` (the Wayland app id), `StartupWMClass`. ([12](12-desktop-integration.md))
4. **System Qt only.** PySide6, Kirigami, kirigami-addons and qqc2-desktop-style come from
   pacman, built against one Qt. Never PyPI's PySide6 (it bundles a Qt that cannot load the
   system's Kirigami). Dev venvs use `--system-site-packages`. ([03](03-python-pyside6.md))
5. **The GUI thread never waits.** Disk, network, decoding, sqlite and subprocess parsing
   run on a worker; results come back through a queued signal. ([09](09-async-commands-files.md))
6. **QML never reaches into the domain.** It binds to controller properties and calls
   slots; controllers never reach into QML. Domain code never imports Qt. ([01](01-architecture.md))
7. **Feedback is layered:** toast → inline message → placeholder → busy/progress →
   dialog → desktop notification (only when the window is not active). ([08](08-user-feedback.md))
8. **Hand things to the desktop:** native file dialogs (portal / Dolphin), `FileManager1` to
   reveal files, `QDesktopServices` for default apps, KNotifications for notifications.
9. **Every user-visible string goes through `i18n()`** (gettext catalogs, KDE style), also
   in Python. ([10](10-i18n.md))
10. **XDG directories:** config `~/.config/<app>rc`, state `~/.local/state/<app>`, cache
    `~/.cache/<app>` (size-budgeted), data `~/.local/share/<app>`. ([11](11-storage-and-cache.md))
11. **Any QML warning fails the test suite.** ([14](14-testing-and-tooling.md))
12. **Packages validate themselves** in `check()`: desktop file, AppStream, QML in the
    wheel, tests against the installed wheel. ([13](13-packaging-pacman.md))

## Python or C++?

| | Python (PySide6) | C++ (Qt + KF6) |
| --- | --- | --- |
| Iteration speed | Edit QML/Python, rerun | Rebuild |
| KDE Frameworks | Bindings exist for KCoreAddons, KNotifications, KStatusNotifierItem, KGuiAddons, KWidgetsAddons, KXmlGui… **not** for KI18n, KDBusService, KCrash, KConfig, KIO — use the stand-ins in [03](03-python-pyside6.md) | Everything |
| Translations | gettext via a context object ([10](10-i18n.md)) | KI18n native |
| Static QML checking | Python types are opaque `QtObject` to qmllint | Full (`QML_ELEMENT`, typed) |
| Packaging | `arch=any`, wheel + `python -m installer` | `arch=x86_64`, `cmake --install` |
| Pick it when | The domain is Python (scraping, ML, data), or prototyping | Performance-sensitive views, deep KDE integration, KDE-hosted projects |

Both templates implement the same app (image-folder browser with WebP thumbnails, command
runner, settings, about page) so they can be compared side by side; they share the app id,
the settings file and the desktop/AppStream/notification files.

## New-project checklist

- [ ] Copy a template; rename per `src/myapp/__init__.py` (Python) or `CMakeLists.txt` (C++)
- [ ] Choose the app id (`io.github.<user>.<app>`); rename the icon, `.desktop`, metainfo, notifyrc
- [ ] Draw the icon (SVG, wide margin, readable at 16 px); install to `hicolor/scalable/apps/<id>.svg`
- [ ] Map every pyproject dependency to its Arch package in the PKGBUILD (`pacman -Ss '^python-x$'`)
- [ ] `scripts/setup.sh --deps | sudo pacman -S --needed -` then `scripts/setup.sh`
- [ ] Test with Breeze **and** Breeze Dark, a narrow window, keyboard only, `LANGUAGE=pt_BR`
- [ ] `scripts/i18n.sh update` after string changes
- [ ] `scripts/package.sh --srcinfo` after PKGBUILD changes; `scripts/package.sh -si`
- [ ] Keep a CHANGELOG (Keep a Changelog) and Conventional Commits; SemVer tags `vX.Y.Z`
