"""User settings: validated in Python, stored with QSettings, edited by FormCard pages.

The file is ~/.config/myapprc: the name and format a C++/KConfig build of the same app
would use, so the two stay compatible. Window size and last folder are *state*, kept apart
in ~/.local/state/myapp/state.ini: wiping state never loses a choice the user made.
"""

from __future__ import annotations

from dataclasses import dataclass, fields, replace
from typing import Any

from PySide6.QtCore import QObject, QSettings, Signal, Slot

from myapp.core import paths
from myapp.qt.props import qt_property


@dataclass(frozen=True)
class Settings:
    thumbnail_size: int = 160  # in device-independent pixels
    cache_megabytes: int = 256
    command: str = "file --brief"  # run on a file, with its path appended
    show_hidden: bool = False

    def validated(self) -> Settings:
        if not 64 <= self.thumbnail_size <= 512:
            raise ValueError("thumbnail size must be within 64-512")
        if not 16 <= self.cache_megabytes <= 8192:
            raise ValueError("cache size must be within 16-8192 MB")
        if not self.command.strip():
            raise ValueError("the command must not be empty")
        return self


def config_store() -> QSettings:
    return QSettings(str(paths.config_file()), QSettings.Format.IniFormat)


def state_store() -> QSettings:
    return QSettings(str(paths.state_dir() / "state.ini"), QSettings.Format.IniFormat)


def load(store: QSettings) -> Settings:
    defaults = Settings()
    values: dict[str, Any] = {}
    for field in fields(Settings):
        default = getattr(defaults, field.name)
        values[field.name] = store.value(f"General/{field.name}", default, type=type(default))
    try:
        return Settings(**values).validated()
    except ValueError:  # a hand-edited file: fall back rather than refuse to start
        return defaults


def save(store: QSettings, settings: Settings) -> None:
    for field in fields(Settings):
        store.setValue(f"General/{field.name}", getattr(settings, field.name))
    store.sync()


class SettingsController(QObject):
    changed = Signal()
    problemChanged = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._store = config_store()
        self.current = load(self._store)
        self._problem = ""

    def _apply(self, **change: Any) -> None:
        try:
            settings = replace(self.current, **change).validated()
        except ValueError as error:
            self._problem = str(error)
            self.problemChanged.emit()
            return
        self._problem = ""
        self.problemChanged.emit()
        if settings != self.current:
            self.current = settings
            save(self._store, settings)
            self.changed.emit()

    # FormCard delegates edit in place: each setter validates and saves immediately (KDE
    # apps apply settings live; no OK/Apply buttons for simple preferences).
    @Slot(int)
    def setThumbnailSize(self, value: int) -> None:
        self._apply(thumbnail_size=value)

    @Slot(int)
    def setCacheMegabytes(self, value: int) -> None:
        self._apply(cache_megabytes=value)

    @Slot(str)
    def setCommand(self, value: str) -> None:
        self._apply(command=value)

    @Slot(bool)
    def setShowHidden(self, value: bool) -> None:
        self._apply(show_hidden=value)

    thumbnailSize = qt_property(lambda self: self.current.thumbnail_size, int, notify=changed)
    cacheMegabytes = qt_property(lambda self: self.current.cache_megabytes, int, notify=changed)
    command = qt_property(lambda self: self.current.command, str, notify=changed)
    showHidden = qt_property(lambda self: self.current.show_hidden, bool, notify=changed)
    problem = qt_property(lambda self: self._problem, str, notify=problemChanged)
