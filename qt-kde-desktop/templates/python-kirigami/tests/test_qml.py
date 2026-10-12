"""The real window, headless: it loads without a single QML warning, and behaves."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from PySide6.QtCore import QObject, QSize, QUrl
from PySide6.QtQml import (
    QQmlApplicationEngine,
    QQmlComponent,
    QQmlEngine,
    QQmlExpression,
)
from PySide6.QtQuick import QQuickItem
from PySide6.QtQuickControls2 import QQuickStyle

from myapp.app import QML_MAIN
from myapp.qt import i18n
from myapp.qt.controller import AppController
from myapp.qt.images import PROVIDER, ThumbnailProvider
from myapp.qt.worker import Worker


@pytest.fixture(scope="session")
def kirigami(qapp: Any) -> None:
    """Skip, rather than fail, where Kirigami or kirigami-addons are not installed."""
    QQuickStyle.setStyle("org.kde.desktop")  # settable once, before the first engine
    engine = QQmlEngine()
    component = QQmlComponent(engine)
    component.setData(b"import org.kde.kirigami\nimport org.kde.kirigamiaddons.formcard\n"
                      b"import QtQuick\nItem {}", QUrl())
    if component.isError():
        pytest.skip("Kirigami not available: " + component.errorString())


@pytest.fixture
def worker() -> Iterator[Worker]:
    worker = Worker()
    worker.start()
    yield worker
    worker.stop()


@pytest.fixture
def window(kirigami: None, qtbot: Any, worker: Worker, pictures: Path,
           qt_warnings: list[str]) -> Iterator[Any]:
    controller = AppController(worker)
    engine = QQmlApplicationEngine()
    i18n.install(engine)
    engine.addImageProvider(PROVIDER, ThumbnailProvider(controller.cache))
    engine.setInitialProperties({"app": controller})
    engine.load(QUrl.fromLocalFile(str(QML_MAIN)))
    assert engine.rootObjects(), qt_warnings
    root = engine.rootObjects()[0]
    controller.start(root)
    controller.browser_ctl.open(str(pictures))
    root.show()
    qtbot.waitExposed(root)
    qtbot.waitUntil(lambda: controller.browser_ctl.rows.count == 4)
    root.controller = controller
    yield root
    controller.closing()
    root.close()
    del engine
    assert qt_warnings == []


def items(root: QObject) -> list[QQuickItem]:
    found: list[QQuickItem] = []
    pending = [root.contentItem() if hasattr(root, "contentItem") else root]
    while pending:
        item = pending.pop()
        found.append(item)
        pending.extend(item.childItems())
    return found


def by_name(root: QObject, name: str) -> QQuickItem:
    return next(i for i in items(root) if i.objectName() == name)


def test_the_window_shows_the_folder_as_a_grid_with_thumbnails(window: Any, qtbot: Any) -> None:
    grid = by_name(window, "grid")
    assert grid.property("count") == 4
    cache = window.controller.cache.root
    qtbot.waitUntil(lambda: len(list(cache.rglob("*.webp"))) == 2, timeout=5000)


def evaluate(root: QObject, script: str) -> Any:
    """Read QML-only types (OverlayDrawer, PromptDialog, ...) through JS: PySide6 has no
    converter for them, and wrapping them in Python can even abort the process."""
    value, failed = QQmlExpression(QQmlEngine.contextForObject(root), root, script).evaluate()
    assert not failed, script
    return value


def test_the_drawer_collapses_when_the_window_narrows(window: Any, qtbot: Any) -> None:
    window.resize(QSize(1400, 800))
    qtbot.waitUntil(lambda: evaluate(window, "globalDrawer.collapsed") is False)
    window.resize(QSize(600, 800))
    qtbot.waitUntil(lambda: evaluate(window, "globalDrawer.collapsed") is True)


def test_every_page_loads(window: Any, qtbot: Any) -> None:
    for name in ("output", "settings", "browser"):
        window.showPage(name)
        qtbot.waitUntil(lambda n=name: window.property("currentPage") == n)


def test_warming_thumbnails_reports_progress_then_finishes(window: Any, qtbot: Any) -> None:
    browser = window.controller.browser_ctl
    messages: list[str] = []
    window.controller.message.connect(messages.append)
    browser.warmThumbnails()
    qtbot.waitUntil(lambda: browser.progress < 0 and bool(messages), timeout=5000)
    assert "Prepared 2 thumbnails" in messages


def test_a_command_streams_its_output(window: Any, qtbot: Any, pictures: Path) -> None:
    browser = window.controller.browser_ctl
    window.controller.settings_ctl.setCommand("echo hello")
    position = next(i for i, r in enumerate(browser.rows.rows()) if r.title == "notes.txt")
    browser.runCommand(position)
    qtbot.waitUntil(lambda: browser.output.count == 1 and not browser.runner.running)
    assert browser.output.rows()[0].title == f"hello {pictures / 'notes.txt'}"


def test_a_missing_program_is_reported_not_crashed(window: Any, qtbot: Any) -> None:
    problems: list[str] = []
    window.controller.problem.connect(problems.append)
    window.controller.settings_ctl.setCommand("no-such-program-xyz")
    window.controller.browser_ctl.runCommand(0)
    qtbot.waitUntil(lambda: bool(problems))
    assert "not installed" in problems[0]


def test_the_about_page_opens(window: Any, qtbot: Any) -> None:
    window.showAbout()
    qtbot.wait(50)


@pytest.fixture
def pt_br(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import subprocess

    out = tmp_path / "locale" / "pt_BR" / "LC_MESSAGES" / "myapp.mo"
    out.parent.mkdir(parents=True)
    po = Path(__file__).resolve().parents[1] / "po" / "pt_BR.po"
    subprocess.run(["msgfmt", "-o", str(out), str(po)], check=True)
    monkeypatch.setattr(i18n, "DEV_LOCALEDIR", tmp_path / "locale")
    monkeypatch.setenv("LANGUAGE", "pt_BR")


def test_the_window_speaks_the_users_language(pt_br: None, window: Any) -> None:
    assert window.property("title") == "Meu App"
    assert evaluate(window, "pageStack.currentItem.title") == "pictures"
    assert evaluate(window, "globalDrawer.actions[2].text") == "Configurações"
