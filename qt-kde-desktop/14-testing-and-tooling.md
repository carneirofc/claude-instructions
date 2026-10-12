# 14 — Testing & tooling

## Headless Qt tests (pytest-qt)

[`tests/conftest.py`](templates/python-kirigami/tests/conftest.py):

```python
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")         # before any Qt import
os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "org.kde.desktop")

@pytest.fixture(autouse=True)
def xdg(tmp_path, monkeypatch):                                # never touch the real home
    for name in ("CONFIG", "STATE", "CACHE", "DATA"):
        monkeypatch.setenv(f"XDG_{name}_HOME", str(tmp_path / name.lower()))

@pytest.fixture
def qt_warnings():                                             # ANY QML warning fails the test
    seen = []
    def handler(kind, _ctx, message):
        if kind != QtMsgType.QtDebugMsg and message not in IGNORED_EXACT \
                and not any(i in message for i in IGNORED):
            seen.append(message)
    previous = qInstallMessageHandler(handler)
    yield seen
    qInstallMessageHandler(previous)
```

`pyproject.toml`: `[tool.pytest.ini_options] qt_api = "pyside6"`; dev group `pytest`,
`pytest-qt` (Arch: `python-pytest-qt`).

Known Kirigami noise to ignore (both reference apps): `"was not placed in the graphics
scene"`, and an exact `'""'` logged by kirigami-addons' AboutPage. Use a message handler,
not `caplog` (scraper found caplog doesn't see them).

## The real window under test

[`tests/test_qml.py`](templates/python-kirigami/tests/test_qml.py):

```python
@pytest.fixture(scope="session")
def kirigami(qapp):                       # skip (not fail) where Kirigami isn't installed
    QQuickStyle.setStyle("org.kde.desktop")   # settable once per process, before any engine
    component = QQmlComponent(QQmlEngine())
    component.setData(b"import org.kde.kirigami\nimport org.kde.kirigamiaddons.formcard\n"
                      b"import QtQuick\nItem {}", QUrl())
    if component.isError(): pytest.skip(component.errorString())

@pytest.fixture
def window(kirigami, qtbot, worker, pictures, qt_warnings):
    controller = AppController(worker)
    engine = QQmlApplicationEngine(); i18n.install(engine)
    engine.addImageProvider(PROVIDER, ThumbnailProvider(controller.cache))
    engine.setInitialProperties({"app": controller})
    engine.load(QUrl.fromLocalFile(str(QML_MAIN)))
    root = engine.rootObjects()[0]
    controller.start(root); controller.browser_ctl.open(str(pictures))
    root.show(); qtbot.waitExposed(root)
    qtbot.waitUntil(lambda: controller.browser_ctl.rows.count == 4)
    yield root
    controller.closing(); root.close(); del engine
    assert qt_warnings == []
```

What the template covers (18 tests, ~2.5 s): every page loads warning-free; thumbnails are
rendered to WebP; the drawer collapses when the window narrows; long-task progress then
completion toast; a command streams output; a missing program is reported, not crashed;
the About page opens; the window speaks pt_BR; core thumbnail/eviction/sqlite/scan logic.

Techniques:
- **Call QML functions from Python**: `window.showPage("settings")`, `window.showAbout()`.
- **Read QML-only types via JS**, not Python wrappers:
  ```python
  value, failed = QQmlExpression(QQmlEngine.contextForObject(root), root, "globalDrawer.collapsed").evaluate()
  ```
- **Find items** by `objectName` while walking `contentItem().childItems()`; set
  `objectName` on views and popups precisely for this.
- **Real input**: `QTest.keyClick(window, Qt.Key.Key_Right, modifiers)`,
  `QTest.mouseClick(window, Qt.LeftButton, pos=item.mapToScene(...))`.
- **Responsiveness**: `window.resize(QSize(1400, 800))` vs `QSize(700, 800)` and assert the
  page stack / drawer state (scraper asserts the detail column appears and disappears).
- **Fast debounces**: monkeypatch delay constants down (`RELOAD_DELAY = 10`).
- **No external services**: fzonetrack points the backend at `http://127.0.0.1:9` and
  injects data through controller internals; scraper serves fixture pages locally.
- **Optional bindings**: test fallbacks with `monkeypatch.setitem(sys.modules,
  "KStatusNotifierItem", None)` so nothing registers on the real session bus.
- Isolate `QSettings` that use default paths with `QSettings.setPath(fmt, UserScope, tmp)`.

Run: `scripts/dev.sh pytest -q` (or `QT_QPA_PLATFORM=offscreen PYTHONPATH=src python -m
pytest`). The PKGBUILD runs the same suite against the installed wheel.

## qmllint

```sh
/usr/lib/qt6/bin/qmllint -I /usr/lib/qt6/qml src/myapp/qml/Main.qml src/myapp/qml/*/*.qml
```

With Python backends, QML sees controllers as plain `QtObject` and `i18n()` as an
unqualified context function, so two categories are pure noise. Disable them in
`.qmllint.ini` next to the sources and keep everything else (unused imports, type
mismatches, deprecated API, required properties):

```ini
[Warnings]
MissingProperty=disable
UnqualifiedAccess=disable
```

The template is qmllint-clean under that config. Typical real findings it caught: unused
imports, `Loader.item` (QObject) assigned to an `Item` property — fix with
`viewLoader.item as Item`. In C++ projects, `qt_add_qml_module` creates `all_qmllint`
targets with full type information; `KI18n.i18n()` (KF ≥ 6.21) is qmllint-visible.
`qmlformat -i` formats; `qmlls` gives editor completion (point it at `/usr/lib/qt6/qml`).

## Python tooling

- ruff with `per-file-ignores` `N802`/`N815` for the Qt package; mypy with
  `disallow_any_decorated = false` there.
- An import-layering test (scraper `tests/test_code_rules.py`) or a grep in CI: `core/`
  never imports PySide6.
- pre-commit hooks run through `uv run` → set `UV_NO_SYNC=1` (dev.sh) or they reinstall
  PyPI's PySide6.

## Shell & packaging

- `bash -n scripts/*.sh`; `shellcheck` (directives `# shellcheck shell=bash` and
  `# shellcheck source=project.sh` are already in `lib.sh`).
- `desktop-file-validate`, `appstreamcli validate --no-net`, `msgfmt --check`.
- `namcap` on PKGBUILD and the built package.
- `makepkg --printsrcinfo | diff - .SRCINFO` to catch drift.

## Manual checklist before a release

- Breeze light/dark, another colour scheme, a different icon theme, accent colour change.
- 1× and 1.5× scale; narrow (gridUnit·22) and wide windows; keyboard-only run.
- `LANGUAGE=pt_BR` (and a long language) — nothing truncated or untranslated.
- From the menu (not a terminal): correct taskbar icon, single instance, notifications in
  System Settings, file dialogs are Dolphin's/the portal's.
- Uninstall: data kept, nothing left in `/usr`.
