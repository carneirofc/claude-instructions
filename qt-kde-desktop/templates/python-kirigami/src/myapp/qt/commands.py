"""Running external commands without blocking the window.

QProcess lives on the GUI thread and is fully asynchronous: output arrives through
signals as it is produced, so a long command streams into the UI and can be stopped.

Rules:
- an argument list, never a shell string (no quoting bugs, no injection);
- resolve the program first and name the pacman package when it is missing;
- stop politely (SIGTERM), then kill after a grace period;
- a command whose output becomes *data* (exiftool -json, ffprobe) can instead run on the
  worker with asyncio.create_subprocess_exec and return parsed results (see the docs).
"""

from __future__ import annotations

import shlex
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, QStandardPaths, QTimer, Signal, Slot

from myapp.qt.i18n import tr
from myapp.qt.props import qt_property

GRACE_MS = 3000


class CommandRunner(QObject):
    line = Signal(str, bool)  # text, is_error
    finished = Signal(int, str)  # exit code (-1: crashed or failed to start), summary
    runningChanged = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._process = QProcess(self)
        self._process.readyReadStandardOutput.connect(lambda: self._drain(False))
        self._process.readyReadStandardError.connect(lambda: self._drain(True))
        self._process.finished.connect(self._done)
        self._process.errorOccurred.connect(self._failed)
        self._process.stateChanged.connect(self.runningChanged)
        self._partial = {False: "", True: ""}
        self._kill = QTimer(self, singleShot=True, interval=GRACE_MS)
        self._kill.timeout.connect(self._process.kill)
        self._label = ""

    def start(self, command: list[str], cwd: Path | None = None) -> bool:
        if self.running or not command:
            return False
        program = QStandardPaths.findExecutable(command[0])
        if not program:
            self.finished.emit(-1, tr("%1 is not installed", command[0]))
            return False
        self._label = shlex.join(command)
        self._partial = {False: "", True: ""}
        if cwd is not None:
            self._process.setWorkingDirectory(str(cwd))
        self._process.start(program, command[1:])
        return True

    @Slot()
    def stop(self) -> None:
        if self.running:
            self._process.terminate()
            self._kill.start()

    def _drain(self, is_error: bool) -> None:
        raw = (self._process.readAllStandardError() if is_error
               else self._process.readAllStandardOutput())
        text = self._partial[is_error] + bytes(raw.data()).decode(errors="replace")
        *lines, self._partial[is_error] = text.split("\n")
        for item in lines:
            self.line.emit(item, is_error)

    def _done(self, code: int, status: QProcess.ExitStatus) -> None:
        self._kill.stop()
        for is_error, rest in self._partial.items():
            if rest:
                self.line.emit(rest, is_error)
        if status == QProcess.ExitStatus.CrashExit:
            self.finished.emit(-1, tr("%1 stopped", self._label))
        elif code == 0:
            self.finished.emit(0, tr("%1 finished", self._label))
        else:
            self.finished.emit(code, tr("%1 failed with exit code %2", self._label, code))

    def _failed(self, error: QProcess.ProcessError) -> None:
        if error == QProcess.ProcessError.FailedToStart:
            self.finished.emit(-1, tr("Could not start %1: %2", self._label,
                                      self._process.errorString()))

    def _running(self) -> bool:
        return self._process.state() != QProcess.ProcessState.NotRunning

    running = qt_property(_running, bool, notify=runningChanged)


def start_detached(command: list[str], cwd: Path | None = None) -> bool:
    """Fire and forget (open a terminal here, launch an editor): outlives this app."""
    program = QStandardPaths.findExecutable(command[0]) if command else ""
    if not program:
        return False
    ok, _pid = QProcess.startDetached(program, command[1:], str(cwd) if cwd else "")
    return ok
