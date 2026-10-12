"""Headless Qt: the offscreen platform, every XDG dir in a temp dir, QML warnings fail tests."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")  # before any Qt import
os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "org.kde.desktop")

from collections.abc import Iterator  # noqa: E402
from pathlib import Path  # noqa: E402

import pytest  # noqa: E402

pytest.importorskip("PySide6.QtQuick")

from PIL import Image  # noqa: E402
from PySide6.QtCore import QtMsgType, qInstallMessageHandler  # noqa: E402

# Known Kirigami noise, not ours.
IGNORED = ("was not placed in the graphics scene",)
IGNORED_EXACT = ('""',)  # kirigami-addons' AboutPage logs an empty string from C++


@pytest.fixture(autouse=True)
def xdg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    for name in ("CONFIG", "STATE", "CACHE", "DATA"):
        monkeypatch.setenv(f"XDG_{name}_HOME", str(tmp_path / name.lower()))
    return tmp_path


@pytest.fixture
def qt_warnings() -> Iterator[list[str]]:
    seen: list[str] = []

    def handler(kind: QtMsgType, _context: object, message: str) -> None:
        if (kind != QtMsgType.QtDebugMsg and message not in IGNORED_EXACT
                and not any(i in message for i in IGNORED)):
            seen.append(message)

    previous = qInstallMessageHandler(handler)
    yield seen
    qInstallMessageHandler(previous)


@pytest.fixture
def pictures(tmp_path: Path) -> Path:
    folder = tmp_path / "pictures"
    (folder / "album").mkdir(parents=True)
    Image.new("RGB", (1600, 1200), "#3daee9").save(folder / "photo.jpg", quality=90)
    Image.new("RGBA", (800, 800), (246, 116, 0, 128)).save(folder / "logo.png")
    (folder / "notes.txt").write_text("hello\n")
    return folder
