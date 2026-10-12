"""The one object QML receives (``required property QtObject app`` in Main.qml).

It owns the page controllers and routes their feedback: page controllers call
``host.notify()``; QML shows a toast. Controllers never reach into QML.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

from PySide6.QtCore import QLocale, QObject, QUrl, Signal, Slot
from PySide6.QtGui import QWindow

from myapp import APP_ID, DISPLAY_NAME, __version__
from myapp.core import paths
from myapp.core.store import Store
from myapp.core.thumbs import ThumbnailCache
from myapp.qt import desktop
from myapp.qt.browser import BrowserController
from myapp.qt.i18n import tr
from myapp.qt.props import qt_property
from myapp.qt.settings import SettingsController, state_store
from myapp.qt.worker import Worker


class AppController(QObject):
    message = Signal(str)  # a passing confirmation: a short toast
    problem = Signal(str)  # an error: a long toast with a "Details" action

    def __init__(self, worker: Worker, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._worker = worker
        self._state = state_store()
        self._notifier: desktop.Notifier | None = None
        self.settings_ctl = SettingsController(self)
        self.cache = ThumbnailCache(paths.cache_dir() / "thumbnails",
                                    self.settings_ctl.current.cache_megabytes * 1024 * 1024)
        # sqlite objects belong to the thread that made them: the store lives on the serial lane.
        self.store = worker.serial(lambda: Store(paths.data_dir() / "myapp.sqlite"))
        self.settings_ctl.changed.connect(self._budget)
        self.browser_ctl = BrowserController(worker, self.store, self.cache, self.settings_ctl,
                                             self, self)

    def start(self, window: QWindow | None) -> None:
        if window is not None:
            self._notifier = desktop.Notifier(window)
        last = str(self._state.value("browser/folder", "", type=str))
        self.browser_ctl.open(last or str(Path.home()))

    def closing(self) -> None:
        """Before the engine goes: stop what would call back into a dying UI."""
        self.browser_ctl.cancelWarm()
        self.browser_ctl.runner.stop()
        self._state.setValue("browser/folder", self.browser_ctl.folder)
        self._state.sync()
        try:  # shutdown is the one place a short blocking wait on the GUI thread is fine
            self._worker.serial(self.store.result(1).close).result(2)
        except Exception:  # noqa: BLE001 - never block quitting on the database
            pass

    # --- Host ---------------------------------------------------------------------------

    def notify(self, text: str) -> None:
        self.message.emit(text)

    def notify_error(self, text: str) -> None:
        self.problem.emit(text)

    def notify_desktop(self, event: str, title: str, text: str, *, failed: bool = False) -> None:
        if self._notifier is not None:
            self._notifier.notify(event, title, text, failed=failed)

    # --- for QML ------------------------------------------------------------------------

    def _budget(self) -> None:
        self.cache.budget_bytes = self.settings_ctl.current.cache_megabytes * 1024 * 1024

    @Slot()
    def clearCache(self) -> None:
        empty = replace(self.cache, budget_bytes=0)
        self._worker.call(empty.evict).then(
            lambda freed: self.notify(tr("Freed %1", QLocale().formattedDataSize(freed))),
            error=self.notify_error)

    @Slot(int, int)
    def saveWindow(self, width: int, height: int) -> None:
        # Size only: on Wayland the compositor owns placement, and should everywhere.
        self._state.setValue("window/width", width)
        self._state.setValue("window/height", height)

    @Slot(result=str)
    def quitBlocker(self) -> str:
        """Non-empty: why quitting now loses work (QML asks before closing)."""
        if self.browser_ctl.progress >= 0:
            return tr("Thumbnails are still being prepared.")
        if self.browser_ctl.runner.running:
            return tr("A command is still running.")
        return ""

    @Slot(QUrl, result=str)
    def localPath(self, url: QUrl) -> str:
        return url.toLocalFile()

    def _about(self) -> dict[str, Any]:
        """KAboutData's shape, for kirigami-addons' FormCard.AboutPage."""
        return {
            "displayName": DISPLAY_NAME,
            "componentName": "myapp",
            "productName": "myapp",
            "programLogo": APP_ID,
            "shortDescription": tr("Browse image folders with a native look"),
            "homepage": "https://example.org/myapp",
            "bugAddress": "https://example.org/myapp/issues",
            "version": __version__,
            "otherText": "",
            "authors": [{"name": "Your Name", "task": tr("Author"), "emailAddress": "",
                         "webAddress": "", "ocsUsername": ""}],
            "credits": [],
            "releases": [],  # [{"version": "0.2.0", "description": "...", "date": "..."}]
            "translators": [],
            "licenses": [{"name": "MIT", "text": "", "spdx": "MIT"}],
            "copyrightStatement": "© 2026 Your Name",
            "desktopFileName": APP_ID,
        }

    def _width(self) -> int:
        return int(self._state.value("window/width", 0, type=int))

    def _height(self) -> int:
        return int(self._state.value("window/height", 0, type=int))

    browser = qt_property(lambda self: self.browser_ctl, QObject)
    settings = qt_property(lambda self: self.settings_ctl, QObject)
    aboutData = qt_property(_about, dict)
    iconSource = qt_property(lambda self: desktop.app_icon_source(), str)
    windowWidth = qt_property(_width, int)
    windowHeight = qt_property(_height, int)
