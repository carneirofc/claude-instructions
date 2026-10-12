"""The folder browser: scanning, thumbnails, file actions, external commands.

Every slow step (scan, thumbnail warm-up, cache eviction, the database) runs on the worker;
this controller only flips state and feeds the model on the GUI thread.
"""

from __future__ import annotations

import shlex
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from PySide6.QtCore import (
    QFileSystemWatcher,
    QLocale,
    QMimeDatabase,
    QObject,
    QTimer,
    QUrl,
    Signal,
    Slot,
)

from myapp.core import scan
from myapp.core.thumbs import ThumbnailCache
from myapp.qt import desktop
from myapp.qt.commands import CommandRunner
from myapp.qt.i18n import tr, trp
from myapp.qt.images import thumbnail_url
from myapp.qt.models import Row, RowsModel
from myapp.qt.props import qt_property

if TYPE_CHECKING:
    from myapp.core.store import Store
    from myapp.qt.settings import SettingsController
    from myapp.qt.worker import Pending, Worker

RELOAD_DELAY_MS = 300  # coalesce a burst of file-system events into one rescan


class Host(Protocol):
    """What a page controller may ask of the app (implemented by AppController)."""

    def notify(self, text: str) -> None: ...
    def notify_error(self, text: str) -> None: ...
    def notify_desktop(self, event: str, title: str, text: str, *,
                       failed: bool = False) -> None: ...


class BrowserController(QObject):
    changed = Signal()
    busyChanged = Signal()
    progressChanged = Signal()
    recentChanged = Signal()

    def __init__(self, worker: Worker, store: Pending[Store], cache: ThumbnailCache,
                 settings: SettingsController, host: Host, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._worker = worker
        self._store = store
        self._cache = cache
        self._settings = settings
        self._host = host
        self._mime = QMimeDatabase()
        self._folder = Path.home()
        self._error = ""
        self._busy = 0
        self._progress = -1.0  # <0: no long task
        self._warm: Pending[int] | None = None
        self._scan: Pending[list[scan.Entry]] | None = None
        self._recent: list[str] = []
        self.rows = RowsModel(self)
        self.output = RowsModel(self)  # the command's output lines
        self.runner = CommandRunner(self)
        self.runner.line.connect(self._output_line)
        self.runner.finished.connect(self._command_done)
        self._watcher = QFileSystemWatcher(self)
        self._reload = QTimer(self, singleShot=True, interval=RELOAD_DELAY_MS)
        self._reload.timeout.connect(self.reload)
        self._watcher.directoryChanged.connect(lambda _path: self._reload.start())
        settings.changed.connect(self.reload)

    # --- navigation ---------------------------------------------------------------------

    @Slot(str)
    def open(self, path: str) -> None:
        folder = Path(path).expanduser()
        if not folder.is_dir():
            self._host.notify_error(tr("%1 is not a folder", path))
            return
        if self._watcher.directories():
            self._watcher.removePaths(self._watcher.directories())
        self._watcher.addPath(str(folder))
        self._folder = folder
        self.changed.emit()
        self.reload()
        self._store.then(lambda store: self._worker.serial(
            lambda: (store.remember_folder(str(folder)), store.recent_folders())[1]
        ).then(self._set_recent))

    @Slot(QUrl)
    def openUrl(self, url: QUrl) -> None:
        """From FolderDialog.selectedFolder or a drop: a file:// URL."""
        local = Path(url.toLocalFile())
        self.open(str(local if local.is_dir() else local.parent))

    @Slot()
    def up(self) -> None:
        if self._folder.parent != self._folder:
            self.open(str(self._folder.parent))

    @Slot()
    def reload(self) -> None:
        if self._scan is not None:
            self._scan.cancel()  # a newer scan wins; the old one's result is dropped
        folder, hidden = self._folder, self._settings.current.show_hidden
        self._loading(True)
        self._scan = self._worker.call(lambda: scan.list_folder(folder, show_hidden=hidden))
        self._scan.then(
            lambda entries: self._show(folder, entries),
            error=self._scan_failed,
            finally_=lambda: self._loading(False),
        )

    def _show(self, folder: Path, entries: list[scan.Entry]) -> None:
        if folder != self._folder:  # the user moved on while this scan ran
            return
        self._error = ""
        self.rows.set_rows([self._row(entry) for entry in entries])
        self.changed.emit()

    def _scan_failed(self, text: str) -> None:
        if text == "cancelled":
            return
        self._error = text
        self.rows.set_rows([])
        self.changed.emit()

    def _row(self, entry: scan.Entry) -> Row:
        locale = QLocale()
        if entry.is_dir:
            return Row(entry.path, entry.name, tr("Folder"), "folder", isFolder=True)
        mime = self._mime.mimeTypeForFile(entry.path, QMimeDatabase.MatchMode.MatchExtension)
        return Row(
            key=entry.path,
            title=entry.name,
            subtitle=locale.formattedDataSize(entry.size),  # "1.2 MiB", in the user's locale
            iconName=mime.iconName() if mime.isValid() else "text-x-generic",
            thumbnail=thumbnail_url(entry.path) if entry.is_image else "",
            badge=Path(entry.name).suffix.lstrip(".").upper() if entry.is_image else "",
            tone="accent" if entry.is_image else "neutral",
        )

    # --- per-row actions ----------------------------------------------------------------

    def _path(self, position: int) -> Path | None:
        key = self.rows.keyAt(position)
        return Path(key) if key else None

    @Slot(int)
    def activate(self, position: int) -> None:
        if (path := self._path(position)) is None:
            return
        if path.is_dir():
            self.open(str(path))
        elif not desktop.open_with_default_app(path):
            self._host.notify_error(tr("No application can open %1", path.name))

    @Slot(int)
    def reveal(self, position: int) -> None:
        if (path := self._path(position)) is not None:
            desktop.reveal_in_file_manager(path)

    @Slot(int)
    def copyPath(self, position: int) -> None:
        if (path := self._path(position)) is not None:
            desktop.copy_to_clipboard(str(path))
            self._host.notify(tr("Copied %1", str(path)))

    @Slot(int)
    def runCommand(self, position: int) -> None:
        if (path := self._path(position)) is None:
            return
        command = [*shlex.split(self._settings.current.command), str(path)]
        self.output.set_rows([])
        if self.runner.start(command, cwd=self._folder):
            self._host.notify(tr("Running %1", command[0]))

    def _output_line(self, text: str, is_error: bool) -> None:
        rows = self.output.rows()
        rows.append(Row(str(len(rows)), text, tone="bad" if is_error else "neutral"))
        self.output.set_rows(rows)

    def _command_done(self, code: int, summary: str) -> None:
        if code == 0:
            self._host.notify(summary)
        else:
            self._host.notify_error(summary)

    # --- long task with progress and cancel ---------------------------------------------

    @Slot()
    def warmThumbnails(self) -> None:
        """Render every thumbnail of the folder ahead of scrolling. Shows the pattern: a
        worker job reporting progress through worker.post(), cancellable, notifying the
        desktop when it ends while the window is in the background."""
        if self._warm is not None:
            return
        images = [Path(row.key) for row in self.rows.rows() if row.thumbnail]
        if not images:
            self._host.notify(tr("No images to prepare here"))
            return
        edge = self._settings.current.thumbnail_size * 2  # HiDPI headroom; bucketed anyway
        cache, post = self._cache, self._worker.post

        async def job() -> int:
            import asyncio

            done = 0
            for position, image in enumerate(images, start=1):
                if await asyncio.to_thread(cache.get, image, edge) is not None:
                    done += 1
                fraction = position / len(images)
                post(lambda f=fraction: self._set_progress(f))
            await asyncio.to_thread(cache.evict)
            return done

        self._set_progress(0.0)
        self._warm = self._worker.run(job)
        self._warm.then(self._warmed, error=self._warm_failed, finally_=self._warm_ended)

    @Slot()
    def cancelWarm(self) -> None:
        if self._warm is not None:
            self._warm.cancel()

    def _warmed(self, count: int) -> None:
        text = trp("Prepared %1 thumbnail", "Prepared %1 thumbnails", count)
        self._host.notify(text)
        self._host.notify_desktop("thumbnailsReady", tr("Thumbnails ready"), text)

    def _warm_failed(self, text: str) -> None:
        if text == "cancelled":
            self._host.notify(tr("Stopped preparing thumbnails"))
        else:
            self._host.notify_error(text)
            self._host.notify_desktop("taskFailed", tr("Thumbnails failed"), text, failed=True)

    def _warm_ended(self) -> None:
        self._warm = None
        self._set_progress(-1.0)

    def _set_progress(self, value: float) -> None:
        self._progress = value
        self.progressChanged.emit()

    # --- state for QML ------------------------------------------------------------------

    def _loading(self, on: bool) -> None:
        self._busy += 1 if on else -1
        self.busyChanged.emit()

    def _set_recent(self, recent: list[str]) -> None:
        self._recent = recent
        self.recentChanged.emit()

    def _empty(self) -> dict[str, str]:
        if self._error:
            return {"icon": "dialog-error", "title": tr("Cannot read this folder"),
                    "hint": self._error}
        return {"icon": "folder-open", "title": tr("This folder is empty"),
                "hint": tr("Drop a folder here, or open another one")}

    folder = qt_property(lambda self: str(self._folder), str, notify=changed)
    title = qt_property(lambda self: self._folder.name or "/", str, notify=changed)
    canGoUp = qt_property(lambda self: self._folder.parent != self._folder, bool, notify=changed)
    error = qt_property(lambda self: self._error, str, notify=changed)
    empty = qt_property(_empty, dict, notify=changed)
    busy = qt_property(lambda self: self._busy > 0, bool, notify=busyChanged)
    progress = qt_property(lambda self: self._progress, float, notify=progressChanged)
    recent = qt_property(lambda self: self._recent, "QStringList", notify=recentChanged)
    model = qt_property(lambda self: self.rows, QObject)
    outputModel = qt_property(lambda self: self.output, QObject)
    command = qt_property(lambda self: self.runner, QObject)
