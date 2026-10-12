"""Start the desktop UI the way KDE's own Kirigami apps start.

Order matters:
 1. notifyrc findable, logging and Qt message routing    (before anything can warn)
 2. QApplication, not QGuiApplication                     (org.kde.desktop paints via QStyle)
 3. the KDE style unless the user chose another           (QT_QUICK_CONTROLS_STYLE wins)
 4. icon theme fallback + app identity (desktop file name = app id = Wayland app id)
 5. single instance                                       (a 2nd launch raises the 1st)
 6. engine: i18n context, image provider, the controller as an initial property, load
 7. exec; then tear down in reverse: controller.closing(), engine, worker
"""

from __future__ import annotations

import argparse
import faulthandler
import locale
import logging
import os
import signal
import sys
from pathlib import Path

from myapp import APP_ID, APP_NAME, DISPLAY_NAME, __version__
from myapp.core import paths

QML_MAIN = Path(__file__).resolve().parent / "qml" / "Main.qml"
STYLE = "org.kde.desktop"

log = logging.getLogger(__name__)


def _logging(verbose: bool) -> None:
    state = paths.state_dir()
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler(state / "myapp.log")],
    )
    # No KCrash binding: a native crash still leaves the Python stacks behind.
    faulthandler.enable(open(state / "crash.log", "a"))  # noqa: SIM115 - lives as long as the app


def _route_qt_messages() -> None:
    """QML console.* and Qt warnings into Python logging (a Plasma session drops them)."""
    from PySide6.QtCore import QtMsgType, qInstallMessageHandler

    levels = {QtMsgType.QtDebugMsg: logging.DEBUG, QtMsgType.QtInfoMsg: logging.INFO,
              QtMsgType.QtWarningMsg: logging.WARNING, QtMsgType.QtCriticalMsg: logging.ERROR,
              QtMsgType.QtFatalMsg: logging.CRITICAL}
    qt_log = logging.getLogger("qt")
    qInstallMessageHandler(lambda kind, _ctx, text: qt_log.log(levels.get(kind, 20), "%s", text))


def _c_locale() -> None:
    """QApplication runs setlocale(LC_ALL, ""): parsing (float(), strptime) would follow the
    user's locale. Keep parsing in C; Qt's QLocale still formats for the user."""
    for category in (locale.LC_NUMERIC, locale.LC_TIME):
        locale.setlocale(category, "C")


def _identity(app: object) -> None:
    from PySide6.QtGui import QGuiApplication

    QGuiApplication.setApplicationName(APP_NAME)  # QSettings dirs, notifyrc lookup
    QGuiApplication.setApplicationDisplayName(DISPLAY_NAME)
    QGuiApplication.setApplicationVersion(__version__)
    QGuiApplication.setDesktopFileName(APP_ID)  # Wayland app id: taskbar icon, portal identity
    try:
        from KCoreAddons import KAboutData  # pacman: kcoreaddons (ships the Python binding)
    except ImportError:
        return
    # The binding takes componentName, displayName, version positionally; the rest by setters.
    about = KAboutData(APP_NAME, DISPLAY_NAME, __version__)
    about.setDesktopFileName(APP_ID)
    KAboutData.setApplicationData(about)  # KNotifications and others read it


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="myapp", description=DISPLAY_NAME)
    parser.add_argument("folder", nargs="?", help="folder to open")
    parser.add_argument("-v", "--verbose", action="store_true")
    args, qt_args = parser.parse_known_args(argv)  # leave -platform, -style, ... to Qt

    _logging(args.verbose)
    signal.signal(signal.SIGINT, signal.SIG_DFL)  # Ctrl+C in a terminal quits

    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QIcon
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuickControls2 import QQuickStyle
    from PySide6.QtWidgets import QApplication

    from myapp.qt import desktop, i18n
    from myapp.qt.controller import AppController
    from myapp.qt.images import PROVIDER, ThumbnailProvider, webp_supported
    from myapp.qt.worker import Worker

    desktop.expose_notifyrc()
    _route_qt_messages()
    app = QApplication([sys.argv[0], *qt_args])
    _c_locale()
    if not os.environ.get("QT_QUICK_CONTROLS_STYLE"):
        QQuickStyle.setStyle(STYLE)
    desktop.add_xdg_icon_paths()
    QIcon.setFallbackThemeName("breeze")  # only the fallback: the user's theme stays active
    _identity(app)
    app.setWindowIcon(desktop.app_icon())

    if not desktop.claim_single_instance():
        log.info("already running: raised the existing window")
        return 0
    if not webp_supported():
        log.warning("no WebP support in Qt: install qt6-imageformats for thumbnails")

    worker = Worker()
    worker.start()
    controller = AppController(worker)
    engine = QQmlApplicationEngine()
    i18n.install(engine)
    engine.addImageProvider(PROVIDER, ThumbnailProvider(controller.cache))
    engine.setInitialProperties({"app": controller})
    engine.load(QUrl.fromLocalFile(str(QML_MAIN)))
    try:
        if not engine.rootObjects():
            log.error("the window failed to load; is kirigami/kirigami-addons installed?")
            return 1
        window = engine.rootObjects()[0]
        desktop.AppAdaptor.register(window)
        controller.start(window)
        if args.folder:
            controller.browser_ctl.open(args.folder)
        return app.exec()
    finally:
        controller.closing()
        del engine  # the window goes before the objects it binds to
        worker.stop()
