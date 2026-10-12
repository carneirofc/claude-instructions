# 09 — Async execution, external commands, files & folders

## Choosing the mechanism

| Work | Mechanism | Thread |
| --- | --- | --- |
| HTTP/REST, SSE | `QNetworkAccessManager` + callbacks (fzonetrack `qt/api.py`, `qt/sse.py`) | GUI (already async) |
| A child process with streamed output | `QProcess` (template `qt/commands.py`) | GUI (already async) |
| Coroutines: async libraries (httpx, aiohttp, aiosqlite, playwright), timeouts, cancellation | **asyncio loop on a worker thread** (template `qt/worker.py`) | worker |
| Blocking calls: file I/O, Pillow, parsing, sync SDKs | `worker.call(fn)` → `asyncio.to_thread` | worker's pool |
| sqlite3 (thread-bound connections) | `worker.serial(fn)` — a one-thread executor | serial lane |
| Image decoding for QML | image provider with `ForceAsynchronousImageLoading` | QML loader threads |
| C++ | `QtConcurrent::run` + `QFutureWatcher`, `QThreadPool` | pool |

**Why not QtAsyncio / qasync on the GUI thread?** One slow step — a big decode, a sync SDK
call inside a coroutine — freezes the window. fzonetrack's ADR 0001: services run "on an
asyncio loop on a worker thread, not on the GUI thread through QtAsyncio: a scrape or an LLM
call must never stall the window". scraper adds: the SQLite connection is loop-bound and
qasync lacked Python 3.14 support.

## The worker bridge

[`qt/worker.py`](templates/python-kirigami/src/myapp/qt/worker.py) — the whole trick is a
queued signal carrying closures back to the GUI thread:

```python
class Relay(QObject):                  # created on the GUI thread
    post = Signal(object)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.post.connect(self._run, Qt.ConnectionType.QueuedConnection)
    @Slot(object)
    def _run(self, thunk): thunk()     # runs on the GUI thread
```

```python
worker.run(lambda: client.fetch(url))                 # coroutine
      .then(show, error=host.notify_error, finally_=lambda: loading(False))
worker.call(lambda: scan.list_folder(path)).then(show)   # blocking function
worker.serial(lambda: store.recent_folders()).then(set_recent)
worker.post(lambda: self._set_progress(f))            # from worker code: run on GUI thread
job.cancel()                                          # cancels the asyncio task, even before it started
```

`Pending.then(done, error=, finally_=)`:
- callbacks always run on the GUI thread, in registration order;
- registering after completion replays (asynchronously, never inline);
- errors arrive as display text; cancellation arrives as `"cancelled"` — compare and stay
  quiet for user-initiated cancels;
- `result(timeout)` blocks — tests and image-loader threads only.

**Rules**
1. Worker code never touches a `QObject` (no signals emitted on controllers, no model
   calls). It returns values or `worker.post(...)`s closures.
2. Capture *values*, not `self` state that may change: `folder, hidden = self._folder, ...`
   before `worker.call(lambda: list_folder(folder, hidden))`.
3. **Newest wins**: keep the running `Pending`; cancel it when a newer request starts, and
   drop late results whose input no longer matches (`if folder != self._folder: return`).
   fzonetrack applies the same "stale-answer guard" to debounced validation.
4. **Debounce bursts** with single-shot timers: rescans after file-system events (300 ms),
   reloads after event storms (250 ms), "cursor rests" before loading details (120–400 ms),
   search-as-you-type (200 ms).
5. A busy *counter* (not a bool) when several jobs can overlap.
6. Shutdown: `controller.closing()` → `del engine` → `worker.stop()` (cancels all tasks,
   stops the loop, joins, shuts the serial executor).

**Progress from a coroutine** (template `warmThumbnails`):

```python
async def job() -> int:
    for position, image in enumerate(images, start=1):
        await asyncio.to_thread(cache.get, image, edge)       # cancellation point
        post(lambda f=position / len(images): self._set_progress(f))
    return len(images)
self._warm = self._worker.run(job)
self._warm.then(self._warmed, error=self._warm_failed, finally_=self._warm_ended)
```

**An external library with its own loop/threads** (e.g. an SDK with callbacks): wrap its
callbacks in `worker.post` (or `relay.post.emit`) — the same single entry point back to Qt.
For `concurrent.futures` APIs: `fut.add_done_callback(lambda f: relay.post.emit(partial(done, f)))`.

## External commands

[`qt/commands.py`](templates/python-kirigami/src/myapp/qt/commands.py): `QProcess` on the
GUI thread — fully asynchronous, output arrives as it is produced.

```python
program = QStandardPaths.findExecutable(command[0])
if not program:
    self.finished.emit(-1, tr("%1 is not installed", command[0]))   # name the package in the text
    return False
self._process.start(program, command[1:])           # an argv list — never a shell string
```

- Split user-configured commands with `shlex.split` (`QProcess.splitCommand` in C++), append
  paths as separate arguments — no quoting bugs, no injection.
- Stream: `readyReadStandardOutput/Error` → keep the partial last line per channel → emit
  complete lines; flush the remainder in `finished`.
- Stop politely: `terminate()` (SIGTERM), then `kill()` after a grace timer (3 s).
- Report: exit 0 → toast; non-zero → error toast with the code; `CrashExit` → "stopped";
  `errorOccurred(FailedToStart)` → "Could not start".
- Working directory: `setWorkingDirectory(folder)`. Environment: `QProcessEnvironment` if
  needed (never inherit secrets into untrusted tools unnecessarily).
- Fire-and-forget (open a terminal here, an editor): `QProcess.startDetached(program, args,
  cwd)` — it outlives the app.
- Output that becomes **data** (`exiftool -json`, `ffprobe -print_format json`): run on
  the worker and return parsed results:

  ```python
  async def probe(path: Path) -> dict:
      proc = await asyncio.create_subprocess_exec(
          "ffprobe", "-v", "error", "-print_format", "json", "-show_format", str(path),
          stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
      try:
          out, err = await asyncio.wait_for(proc.communicate(), timeout=30)
      except (asyncio.CancelledError, TimeoutError):
          proc.kill(); await proc.wait(); raise
      if proc.returncode:
          raise RuntimeError(err.decode(errors="replace").strip() or f"exit {proc.returncode}")
      return json.loads(out)
  worker.run(lambda: probe(path)).then(show_info, error=host.notify_error)
  ```
- A child *service* (fzonetrack's backend server): `QProcess` with `MergedChannels`, a
  health-probe `QTimer`, `terminate → waitForFinished(5000) → kill` on `aboutToQuit`, and a
  `prctl(PR_SET_PDEATHSIG, SIGTERM)` trampoline so a crashed UI cannot orphan it.

## Files & folders — hand them to the desktop

| Need | Do | Not |
| --- | --- | --- |
| Pick a folder/file | `QtQuick.Dialogs.FolderDialog`/`FileDialog` → Dolphin's dialog (plasma-integration) or the portal's | a custom picker |
| Convert the picked URL | `@Slot(QUrl) openUrl(url)` → `url.toLocalFile()` | string slicing `file://` in QML |
| Open with the default app | `QDesktopServices.openUrl(QUrl.fromLocalFile(p))` (→ xdg-open/portal/KIO) | `subprocess(["xdg-open"…])` |
| Show in file manager | `org.freedesktop.FileManager1.ShowItems([uri], "")` (folders: `ShowFolders`), fall back to opening the parent; C++: `KIO::highlightInFileManager` | launching `dolphin` |
| Copy a path | `QGuiApplication.clipboard().setText(...)` **from a user action** (Wayland ignores focus-less writes) | clipboard in a timer |
| Drop files/folders in | `DropArea { keys: ["text/uri-list"]; onDropped: d => backend.openUrl(d.urls[0]) }` + an animated highlight | |
| Watch for changes | `QFileSystemWatcher.addPath(folder)` → debounce → rescan | polling |
| Trash instead of delete | `QFile.moveToTrash(path)` (Python/C++), `KIO::trash` (C++, undoable) | `os.remove` for user files |
| List a folder | `os.scandir` on the worker; folders first, case-insensitive (Dolphin's order); skip dotfiles unless asked | `QDir` on the GUI thread |
| Mime type & icon | `QMimeDatabase.mimeTypeForFile(p, MatchExtension).iconName()` | guessing from the suffix |
| Sizes, dates | `QLocale().formattedDataSize(n)`, `QLocale().toString(dt, QLocale.FormatType.ShortFormat)` | `f"{n/1024:.1f} KB"` |

The template's browser ([`qt/browser.py`](templates/python-kirigami/src/myapp/qt/browser.py),
[`BrowserPage.qml`](templates/python-kirigami/src/myapp/qml/pages/BrowserPage.qml)) does all
of the above: Up (Alt+Up / Backspace), Open Folder (Ctrl+O), recent folders (sqlite), grid ⇄
list, context menu (Open / Show in File Manager / Copy Path / Run Command), drop target,
watcher-driven refresh, placeholder per state.

The app also accepts a folder on the command line and declares `MimeType=inode/directory;`
with `Exec=myapp %f` in its `.desktop`, so "Open with → My App" works from Dolphin.
