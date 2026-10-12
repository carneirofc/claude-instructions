"""Async execution: one asyncio loop on one worker thread; results come back on the GUI thread.

    worker.run(lambda: fetch(url)).then(show, error=host.notify_error)   # a coroutine
    worker.call(lambda: scan.list_folder(path)).then(show)               # blocking code
    job.cancel()                                                         # any time

Why not QtAsyncio / qasync on the GUI thread: a slow coroutine step (a big decode, a sync
library call) would freeze the window. Here only the worker waits.

The rule: worker-side code never touches a QObject. The only bridge back is Relay, a
signal with a queued connection whose slot runs closures on the GUI thread.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import threading
from collections.abc import Awaitable, Callable
from functools import partial
from typing import Any

from PySide6.QtCore import QObject, Qt, Signal, Slot

log = logging.getLogger(__name__)

CANCELLED = "cancelled"


class Relay(QObject):
    """Runs closures on the thread this object lives in: create it on the GUI thread."""

    post = Signal(object)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.post.connect(self._run, Qt.ConnectionType.QueuedConnection)

    @Slot(object)
    def _run(self, thunk: Callable[[], None]) -> None:
        thunk()


class Pending[T]:
    """A job on the worker, seen from the GUI thread. Callbacks always run on the GUI thread,
    in order, even when registered after the job ended. Errors arrive as display text."""

    def __init__(self, relay: Relay, future: concurrent.futures.Future[T]) -> None:
        self._relay = relay
        self._future = future
        self._callbacks: list[tuple[Callable[[T], None] | None,
                                    Callable[[str], None] | None,
                                    Callable[[], None] | None]] = []
        self._settled = False
        future.add_done_callback(self._on_worker_done)  # runs on the worker thread

    def then(self, done: Callable[[T], None] | None = None, *,
             error: Callable[[str], None] | None = None,
             finally_: Callable[[], None] | None = None) -> Pending[T]:
        self._callbacks.append((done, error, finally_))
        if self._settled:  # late registration: replay on the GUI thread, never inline
            self._relay.post.emit(self._settle)
        return self

    def cancel(self) -> None:
        # Cancelling the concurrent future cancels the asyncio task, even before it started.
        self._future.cancel()

    def result(self, timeout: float | None = None) -> T:
        """Block for the result: tests and image-loader threads only, never the GUI thread."""
        return self._future.result(timeout)

    def _on_worker_done(self, _future: concurrent.futures.Future[T]) -> None:
        try:
            self._relay.post.emit(self._settle)
        except RuntimeError:  # the relay is gone: the app is shutting down
            pass

    def _settle(self) -> None:
        self._settled = True
        callbacks, self._callbacks = self._callbacks, []
        for done, error, finally_ in callbacks:
            try:
                if self._future.cancelled():
                    if error:
                        error(CANCELLED)
                elif (exc := self._future.exception()) is not None:
                    if error:
                        error(str(exc) or type(exc).__name__)
                    else:
                        log.error("unhandled job error", exc_info=exc)
                elif done:
                    done(self._future.result())
            finally:
                if finally_:
                    finally_()


class Worker(QObject):
    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._relay = Relay(self)
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._main, name="worker", daemon=True)
        # One extra thread for code that must stay on one thread (sqlite3 connections).
        self._serial = concurrent.futures.ThreadPoolExecutor(1, thread_name_prefix="serial")

    def _main(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def start(self) -> None:
        self._thread.start()

    def run[T](self, make: Callable[[], Awaitable[T]]) -> Pending[T]:
        """Run a coroutine on the worker loop. ``make`` is called on the worker."""
        async def job() -> T:
            return await make()
        return Pending(self._relay, asyncio.run_coroutine_threadsafe(job(), self._loop))

    def call[T](self, fn: Callable[[], T]) -> Pending[T]:
        """Run blocking code (file I/O, Pillow, sqlite) in the loop's thread pool."""
        return self.run(partial(asyncio.to_thread, fn))

    def serial[T](self, fn: Callable[[], T]) -> Pending[T]:
        """Run blocking code on the one serial thread, in submission order (the database)."""
        return self.run(lambda: asyncio.get_running_loop().run_in_executor(self._serial, fn))

    def post(self, fn: Callable[[], Any]) -> None:
        """From worker-side code: run ``fn`` on the GUI thread (progress, partial results)."""
        self._relay.post.emit(fn)

    def stop(self, timeout: float = 5.0) -> None:
        """Cancel what runs, then stop and join the thread. Call after the QML engine is gone."""
        if not self._thread.is_alive():
            return

        async def cancel_all() -> None:
            tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

        try:
            asyncio.run_coroutine_threadsafe(cancel_all(), self._loop).result(timeout)
        except (TimeoutError, concurrent.futures.TimeoutError):
            log.warning("worker tasks did not stop within %ss", timeout)
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout)
        self._serial.shutdown(wait=True, cancel_futures=True)
