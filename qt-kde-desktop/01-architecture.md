# 01 — Architecture

## Layers

```
┌──────────────────────────────── QML (pages, components) ───────────────────────────────┐
│  binds to properties, calls slots, shows toasts; Kirigami.Theme/Units only              │
└──────────────▲──────────────────────────────────────────────────┬──────────────────────┘
               │ properties + change signals                       │ slots (QVariantMap forms)
┌──────────────┴──────────── Qt glue (controllers, models, providers) ▼────────────────────┐
│  AppController (the one object QML receives) → page controllers, list models,           │
│  image provider, command runner, desktop integration; runs on the GUI thread            │
└──────────────▲──────────────────────────────────────────────────┬──────────────────────┘
               │ results via Relay (queued signal)                 │ worker.run/call/serial
┌──────────────┴──────────────────── Worker thread ─────────────────▼────────────────────┐
│  asyncio loop + thread pool + one serial lane (sqlite)                                   │
└──────────────▲──────────────────────────────────────────────────┬──────────────────────┘
               │                                                    │
┌──────────────┴───────────── Domain (no Qt import) ────────────────▼────────────────────┐
│  scanning, thumbnails, storage, network clients, parsing — testable without Qt          │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

Package layout (Python template, [`templates/python-kirigami`](templates/python-kirigami)):

```
src/myapp/
  __init__.py        APP_ID, APP_NAME, DISPLAY_NAME, __version__
  app.py             bootstrap (02, 03)
  core/              domain: paths.py scan.py thumbs.py store.py   ← no PySide6 import
  qt/                glue: controller.py browser.py settings.py models.py worker.py
                     images.py commands.py desktop.py i18n.py props.py
  qml/               Main.qml pages/ components/
  data/              icons/<APP_ID>.svg  knotifications6/<APP_NAME>.notifyrc
po/                  myapp.pot, <lang>.po
packaging/arch/      PKGBUILD .SRCINFO <APP_ID>.desktop <APP_ID>.metainfo.xml
scripts/             lib.sh project.sh setup.sh dev.sh build.sh install.sh package.sh i18n.sh
tests/               conftest.py test_core.py test_qml.py test_i18n.py
```

fzonetrack enforces the boundary mechanically (`grep -l PySide6 core/*.py` is empty);
scraper has a `tests/test_code_rules.py` that asserts import layering. Do one of the two.

## Exposing Python objects to QML

Three mechanisms; use the first, the second when you need a QML import, the third only
for functions that must be global.

**1. Initial property (recommended, scraper + template).** One root object; type-safe
because QML declares it `required`.

```python
engine.setInitialProperties({"app": controller})
engine.load(QUrl.fromLocalFile(str(QML_MAIN)))
```
```qml
Kirigami.ApplicationWindow {
    required property QtObject app
}
// pages: readonly property QtObject app: applicationWindow().app
```

Sub-controllers are constant `QObject` properties: `app.browser.model`, `app.settings.command`.

**2. Registered singleton (fzonetrack).** QML does `import io.github.carneirofc.fzonetrack`
and uses `Backend.library`. The instance is built in Python first and handed over:

```python
QML_IMPORT_NAME = "io.github.carneirofc.fzonetrack"
QML_IMPORT_MAJOR_VERSION = 1

@QmlElement
@QmlSingleton
class Backend(QObject):
    @staticmethod
    def create(_engine):
        assert _instance is not None, "install() the Backend before loading QML"
        return _instance
```

The module containing it must be imported before `engine.load`. In C++ this is the norm:
`QML_ELEMENT` + `QML_SINGLETON` inside `qt_add_qml_module` ([04](04-cpp-kf6.md)).

**3. Context object** — only for the `i18n()` family ([10](10-i18n.md)):
`engine.rootContext().setContextObject(ctx)` makes its slots global functions.

Avoid `setContextProperty`: untyped, invisible to tooling, slower.

## Controllers

- **Root controller owns page controllers and routes feedback.** Page controllers depend on
  a `Host` protocol (`notify`, `notify_error`, `notify_desktop`), not on the root class.
  The root emits `message(str)` / `problem(str)`; `Main.qml` turns them into toasts. Nothing
  in Python touches QML items.
- **Properties are read-only from QML; writes go through slots** that validate
  (`setThumbnailSize(int)`), so invalid input is rejected in one place and surfaced as a
  `problem` property next to the field.
- **Boilerplate killer**: [`qt/props.py`](templates/python-kirigami/src/myapp/qt/props.py)

  ```python
  count = qt_property(_count, int, notify=countChanged)   # notify → bindable
  model = qt_property(lambda self: self.rows, QObject)    # no notify → constant
  ```
- **Coarse vs fine signals.** One `changed` signal for a group of related properties is
  fine (fzonetrack); split when a group changes often and others are expensive to rebind.
- **Forms**: QML sends a JS object to `@Slot("QVariantMap")`; validate into a frozen model
  with `extra="forbid"` (pydantic in scraper) so a renamed QML key fails loudly.
- **Gotcha (PySide6)**: a `Property` whose `notify` signal is declared on a *base class*
  crashes. Declare the property on the base class behind an overridable hook.

## List models

[`qt/models.py`](templates/python-kirigami/src/myapp/qt/models.py): rows are frozen
dataclasses; roles are an `IntEnum` whose names equal the fields and the delegates'
`required property` names.

```python
class Role(IntEnum):
    key = Qt.ItemDataRole.UserRole + 1
    title = auto()
    ...
def roleNames(self):
    return {role.value: QByteArray(role.name.encode()) for role in Role}
```

| Change | Signal | Why |
| --- | --- | --- |
| New list | `beginResetModel/endResetModel` | simple; use `populate` transitions to soften |
| Re-sort | `layoutAboutToBeChanged/layoutChanged` | delegates survive; selection by key survives |
| One row changed | `dataChanged(index, index, [roles])` | cheapest repaint, animations keep running |
| Append (logs) | `beginInsertRows/endInsertRows` (+ `beginRemoveRows` to cap) | no full rebind |

Rules learned the hard way:
- Keep selection/current row **by key**, not by index (scraper) — reloads and sorts keep it.
- Roles are fixed when the model is created: every row must carry every role (fzonetrack).
- Give only the **visible** view a model (`model: gridMode ? rows : null`) — the hidden
  grid/list then builds nothing (fzonetrack).
- `reuseItems: true` needs per-delegate state reset in `ListView.onReused`.

One generic row record + one delegate per layout (scraper's `RowView` → `RowDelegate` /
`CoverCard`) means a new page is a mapping function, not new QML.

## Threads

See [09](09-async-commands-files.md). Summary: GUI thread for Qt objects; one worker thread
with an asyncio loop (fzonetrack's ADR: *"a scrape or an LLM call must never stall the
window"*, so not QtAsyncio on the GUI thread); a serial lane for sqlite; QML's own
image-loader threads for providers; `QProcess`/`QNetworkAccessManager` are already
asynchronous on the GUI thread.

## Shutdown order

```python
try:
    return app.exec()
finally:
    controller.closing()   # stop timers, cancel jobs, stop processes, save state
    del engine             # the window goes before the objects it binds to
    worker.stop()          # cancel tasks, stop the loop, join
```

Destroying controllers while the window still exists lets its bindings run against
half-destroyed objects; stopping the worker before `closing()` lets late callbacks hit a
dead relay (the template's `Pending` swallows exactly that `RuntimeError`).

## Ports (when the backend can be remote or in-process)

fzonetrack's controllers depend on `Protocol` ports (`LibraryPort`, `SettingsPort`) with
an `Http*Port` (REST + SSE on `QNetworkAccessManager`) and an `InProcess*Port` (worker
loop) implementation, and map in-process errors to the HTTP status codes REST would give —
controllers cannot tell the transports apart. Use this when a UI must work both as a
client of a service and standalone.
