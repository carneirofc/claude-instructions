"""Handing things to the desktop: single instance, file manager, default apps, notifications.

Every call goes through a freedesktop/KDE service, so the user's choices apply: their file
manager (FileManager1: Dolphin, Nautilus, ...), their default apps (QDesktopServices →
xdg-open/portal/KIO), their notification settings (KNotifications → System Settings →
Notifications → My App).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from PySide6.QtCore import ClassInfo, QObject, QUrl, Slot
from PySide6.QtDBus import QDBusConnection, QDBusInterface, QDBusMessage
from PySide6.QtGui import QDesktopServices, QGuiApplication, QIcon, QWindow

from myapp import APP_ID, APP_NAME

log = logging.getLogger(__name__)

DATA = Path(__file__).resolve().parent.parent / "data"
BUNDLED_ICON = DATA / "icons" / f"{APP_ID}.svg"
INTERFACE = f"{APP_ID}.App"

# --- single instance (KDBusService has no Python binding: plain QtDBus) -----------------


def claim_single_instance() -> bool:
    """Own the app id on the session bus; False when another instance already does (it is
    asked to raise its window). No bus (a sandbox, a test): run anyway."""
    bus = QDBusConnection.sessionBus()
    if not bus.isConnected() or bus.registerService(APP_ID):
        return True
    QDBusInterface(APP_ID, "/", INTERFACE, bus).call("activate")
    return False


@ClassInfo({"D-Bus Interface": INTERFACE})
class AppAdaptor(QObject):
    def __init__(self, window: QWindow) -> None:
        super().__init__(window)
        self._window = window

    @Slot()
    def activate(self) -> None:
        self._window.show()
        self._window.raise_()
        self._window.requestActivate()

    @classmethod
    def register(cls, window: QObject) -> None:
        if isinstance(window, QWindow):
            QDBusConnection.sessionBus().registerObject(
                "/", cls(window), QDBusConnection.RegisterOption.ExportAllSlots)


# --- icons -------------------------------------------------------------------------------


def app_icon() -> QIcon:
    """The installed theme icon (the user's icon theme may restyle it), else the bundled SVG."""
    return QIcon.fromTheme(APP_ID, QIcon(str(BUNDLED_ICON)))


def app_icon_source() -> str:
    """For Kirigami.Icon / titleIcon: a theme name when installed, else a file URL."""
    if QIcon.hasThemeIcon(APP_ID):
        return APP_ID
    return QUrl.fromLocalFile(str(BUNDLED_ICON)).toString()


def add_xdg_icon_paths() -> None:
    """A Qt built elsewhere may not search the XDG icon dirs (user installs land there)."""
    home = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local/share")
    dirs = [home, *(os.environ.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share").split(":")]
    paths = QIcon.themeSearchPaths()
    for base in dirs:
        icons = str(Path(base) / "icons")
        if base and icons not in paths and Path(icons).is_dir():
            paths.append(icons)
    QIcon.setThemeSearchPaths(paths)


# --- file manager and default applications -----------------------------------------------


def reveal_in_file_manager(path: Path) -> None:
    """Select a file in its folder (or open a folder) in the user's file manager."""
    uri = QUrl.fromLocalFile(str(path)).toString()
    bus = QDBusConnection.sessionBus()
    manager = QDBusInterface("org.freedesktop.FileManager1", "/org/freedesktop/FileManager1",
                             "org.freedesktop.FileManager1", bus)
    if bus.isConnected() and manager.isValid():
        method = "ShowFolders" if path.is_dir() else "ShowItems"
        reply = manager.call(method, [uri], "")
        if reply.type() != QDBusMessage.MessageType.ErrorMessage:
            return
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(path if path.is_dir() else path.parent)))


def open_with_default_app(path: Path) -> bool:
    return QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))


def copy_to_clipboard(text: str) -> None:
    """Call only from a user action: Wayland ignores clipboard writes without input focus."""
    QGuiApplication.clipboard().setText(text)


# --- notifications -----------------------------------------------------------------------


def expose_notifyrc() -> None:
    """KNotifications only fires events listed in $XDG_DATA_DIRS/knotifications6/<app>.notifyrc.
    A package installs it to /usr/share; a source checkout prepends data/. Call first thing."""
    name = Path("knotifications6") / f"{APP_NAME}.notifyrc"
    home = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local/share")
    dirs = (os.environ.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share").split(":")
    if not any((Path(d) / name).is_file() for d in [home, *dirs] if d):
        os.environ["XDG_DATA_DIRS"] = ":".join([str(DATA), *dirs])


class Notifier(QObject):
    """Desktop notifications for things that finish while the user looks elsewhere.

    Policy: in-window feedback (toasts, inline messages) is the default; a desktop
    notification only when the window is not active, or for failures of long work."""

    def __init__(self, window: QWindow) -> None:
        super().__init__(window)
        self._window = window
        self._live: set[QObject] = set()

    def notify(self, event: str, title: str, text: str, *, failed: bool = False) -> None:
        if self._window.isActive() and not failed:
            return
        try:
            from KNotifications import KNotification  # pacman: knotifications
        except ImportError:
            log.info("%s: %s", title, text)
            return
        note = KNotification(event, parent=self)  # event id: an [Event/<id>] in the notifyrc
        note.setTitle(title)
        note.setText(text)
        note.setIconName(APP_ID if QIcon.hasThemeIcon(APP_ID) else "dialog-information")
        note.setWindow(self._window)  # Plasma: clicking it raises this window
        if failed:
            note.setUrgency(KNotification.Urgency.HighUrgency)
        note.addDefaultAction("Open").activated.connect(self._raise)
        self._live.add(note)  # the Python wrapper must outlive the popup for actions to fire
        note.closed.connect(lambda: self._live.discard(note))
        note.sendEvent()

    def _raise(self) -> None:
        self._window.show()
        self._window.requestActivate()
