# 03 — Python / PySide6

## The dependency rule

Kirigami, kirigami-addons and qqc2-desktop-style are C++ QML plugins compiled against the
distribution's Qt. PyPI's PySide6 wheels ship their *own* Qt, which cannot load them. So:

- `pyproject.toml` lists **no** PySide6 (`dependencies` holds only non-Qt libs);
- dev venv: `uv venv --system-site-packages --python /usr/bin/python`, then
  `uv sync --frozen --no-install-package pyside6 --no-install-package pyside6-essentials
  --no-install-package pyside6-addons --no-install-package shiboken6`;
- `export UV_NO_SYNC=1` in `scripts/dev.sh` — a plain `uv run` (or a pre-commit hook using
  it) would sync PyPI's PySide6 back in;
- user installs export the lock with `uv export --prune pyside6`;
- assert it: `PySide6.__path__[0].startswith("/usr/")` (`check_pyside` in `project.sh`);
- `uv venv --clear` when recreating — a venv built on an older system Python no longer
  imports the system PySide6 after a Python upgrade.

## Bootstrap

[`app.py`](templates/python-kirigami/src/myapp/app.py), in order:

```python
desktop.expose_notifyrc()          # KNotifications finds events (source checkouts)
_route_qt_messages()               # QML console.*/warnings → logging (Plasma drops them)
app = QApplication([sys.argv[0], *qt_args])   # parse_known_args: leave -platform etc. to Qt
_c_locale()                        # see below
if not os.environ.get("QT_QUICK_CONTROLS_STYLE"):
    QQuickStyle.setStyle("org.kde.desktop")
desktop.add_xdg_icon_paths()
QIcon.setFallbackThemeName("breeze")
_identity(app)                     # names, setDesktopFileName(APP_ID), KAboutData
app.setWindowIcon(desktop.app_icon())
if not desktop.claim_single_instance(): return 0
worker = Worker(); worker.start()
controller = AppController(worker)
engine = QQmlApplicationEngine()
i18n.install(engine)
engine.addImageProvider(PROVIDER, ThumbnailProvider(controller.cache))
engine.setInitialProperties({"app": controller})
engine.load(QUrl.fromLocalFile(str(QML_MAIN)))
if not engine.rootObjects(): return 1          # say which package is probably missing
```

Details that matter:
- `signal.signal(SIGINT, SIG_DFL)` — Ctrl+C in the terminal quits (Qt's loop never returns
  to Python to see KeyboardInterrupt).
- **Locale gotcha:** `QApplication` calls `setlocale(LC_ALL, "")`; afterwards `float("1.5")`
  still works but `strptime("%B")` and C-level number parsing follow the user's locale.
  Reset `LC_NUMERIC`/`LC_TIME` to `"C"`; Qt keeps its own `QLocale` for display (scraper).
- `faulthandler.enable(open(state/"crash.log","a"))` — there is no KCrash binding.
- QML loads from the filesystem (`Path(__file__).parent / "qml"`); the wheel must include
  `qml/` (hatchling includes everything under the package; the PKGBUILD's `check()` asserts
  it). Subdirectories are imported by path: `import "../components"`.

## KDE Frameworks from Python

Arch ships Python bindings in the KF packages themselves
(`/usr/lib/python3.14/site-packages/K*.so`): **KCoreAddons, KNotifications,
KStatusNotifierItem, KGuiAddons, KWidgetsAddons, KXmlGui, KJobWidgets, KUnitConversion**.
Import them optionally:

```python
try:
    from KCoreAddons import KAboutData        # pacman: kcoreaddons
except ImportError:
    ...                                       # plain QGuiApplication setters
# The binding takes componentName, displayName, version positionally; the rest via setters.
about = KAboutData(APP_NAME, DISPLAY_NAME, __version__)
about.setDesktopFileName(APP_ID)
KAboutData.setApplicationData(about)
```

No binding → stand-in:

| KDE API | Python stand-in | Where |
| --- | --- | --- |
| KI18n / `KLocalizedContext` | context object with `i18n*` slots backed by gettext | [10](10-i18n.md), `qt/i18n.py` |
| `org.kde.ki18n` QML module | **does not work**: its singleton is created by C++ `setupLocalizedContext`; from Python `KI18n` is null (verified) | — |
| KDBusService (single instance) | `QDBusConnection.registerService(APP_ID)` + exported `activate` slot | `qt/desktop.py` |
| KCrash | `faulthandler` to `$XDG_STATE_HOME/<app>/crash.log` | `app.py` |
| KConfig / KConfigXT | `QSettings(<config>/<app>rc, IniFormat)` — same file a C++ build reads | [11](11-storage-and-cache.md) |
| KIO `highlightInFileManager` | `org.freedesktop.FileManager1.ShowItems` over QtDBus | [09](09-async-commands-files.md) |
| KIO jobs / thumbnails | Pillow + own WebP cache, `QDesktopServices` | [07](07-icons-and-images.md) |
| `KAboutData` for the About page when the binding is absent | pass a dict shaped like KAboutData as `aboutData` | `controller._about()` |

## PySide6 idioms & gotchas

- `QtQml.QQmlImageProviderBase` lives in **QtQml**, not QtQuick (import error otherwise).
- `QTimer(self, singleShot=True, interval=300)` — Qt properties as constructor kwargs.
- Slots that QML calls with JS objects: `@Slot("QVariantMap")`, lists `"QVariantList"`,
  string lists `"QStringList"`, any `"QVariant"`; return types via `result=`.
- Variadic functions for QML: stack one `Slot` overload per arity on the same function
  (template `i18n.py` `_overloads`).
- Keep Python wrappers alive while Qt still needs them: in-flight `QNetworkReply`s in a set
  until `finished`; `QQuickImageResponse` until QML deletes it; a `KNotification` until
  `closed` — or its action never fires (fzonetrack).
- `window.property("globalDrawer")` raises "Can't find converter for OverlayDrawer_QMLTYPE":
  read QML-only types through `QQmlExpression(...).evaluate()` (template test helper).
  Wrapping a `Kirigami.PromptDialog` with `findChild` can even abort in
  `SbkObjectType_Check` (scraper).
- ruff: ignore `N802`/`N815` under the Qt package (camelCase overrides and QML names);
  mypy: `disallow_any_decorated = false` there (`@Slot` returns Any).
- Python ≥ 3.12 generics (`class Pending[T]`) are fine with PySide6 6.11.
- QtAsyncio exists (`PySide6.QtAsyncio`) but runs coroutines on the GUI thread; both
  reference apps rejected it for real work ([09](09-async-commands-files.md)).
