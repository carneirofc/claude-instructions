# 11 — Storage, settings & cache

## Where things go (XDG)

| Kind | Path | Lose it → | Python | C++ |
| --- | --- | --- | --- | --- |
| **Config** (user choices) | `~/.config/<app>rc` | user is annoyed | `QSettings(config/"myapprc", IniFormat)` (`platformdirs.user_config_path()`) | KConfigXT `Config` (`kcfgfile name="myapprc"`) |
| **State** (window size, last folder, layout, sort) | `~/.local/state/<app>/` | nothing important | `QSettings(state/"state.ini", IniFormat)` | `KSharedConfig::openStateConfig()` (`<app>staterc`) |
| **Cache** (thumbnails, HTTP) | `~/.cache/<app>/` | time | size-budgeted dir | `QStandardPaths::CacheLocation` |
| **Data** (the user's library/db) | `~/.local/share/<app>/` | **the user's work** | sqlite | same |
| Logs, crash dumps | `~/.local/state/<app>/` | — | `logging.FileHandler`, `faulthandler` | `KCrash` |

[`core/paths.py`](templates/python-kirigami/src/myapp/core/paths.py) uses `platformdirs`
(Qt-free; honours `$XDG_*_HOME`). Tests point every `XDG_*_HOME` at a temp dir (autouse
fixture) — no test ever touches the real home.

- The config file name/format matches KConfig, so a Python and a C++ build of the same app
  share settings (`[General]` group, same keys).
- Never write config the user didn't change: write on change, not on exit.
- Uninstall keeps data; say so in `install.sh --uninstall` and the `.install` messages.
- UI preferences that are really state (view mode, sort, window size): state file.
  fzonetrack keeps `QSettings("fzonetrack", "fzonetrack-qt")` for those and leaves app
  config to its backend.

## Settings: validate in one place, apply live

[`qt/settings.py`](templates/python-kirigami/src/myapp/qt/settings.py):

```python
@dataclass(frozen=True)
class Settings:
    thumbnail_size: int = 160
    cache_megabytes: int = 256
    command: str = "file --brief"
    show_hidden: bool = False
    def validated(self) -> Settings: ...            # raises ValueError with a user message

class SettingsController(QObject):
    @Slot(int)
    def setThumbnailSize(self, value): self._apply(thumbnail_size=value)
    def _apply(self, **change):
        try: settings = replace(self.current, **change).validated()
        except ValueError as error: self._problem = str(error); ...; return   # shown on the field
        save(self._store, settings); self.changed.emit()
```

- Loading: `store.value(key, default, type=type(default))` — QSettings' INI values are
  strings otherwise; an invalid hand-edited file falls back to defaults rather than refusing
  to start.
- KDE style: simple preferences apply immediately (no OK/Apply). For a draft that must be
  saved as a whole (fzonetrack's server config): a `draft` copy, `dirty = draft != saved`, a
  footer with Save/Revert, `load()` refuses to clobber unsaved edits, and "takes effect
  after restart" warnings computed from the changed keys.
- Secrets never go in config: use the keyring (`python-keyring` → KWallet/Secret Service;
  C++ `QtKeychain`) — fzonetrack's credentials "never ride in the draft".

## Window state

```qml
width: app.windowWidth > 0 ? app.windowWidth : Kirigami.Units.gridUnit * 60
onClosing: app.saveWindow(width, height)        // size only — never the position
```

## Database (sqlite)

[`core/store.py`](templates/python-kirigami/src/myapp/core/store.py):

```python
self._db = sqlite3.connect(path)
self._db.execute("PRAGMA journal_mode=WAL")      # readers (CLI, backup) work during writes
self._db.execute("PRAGMA foreign_keys=ON")
(current,) = self._db.execute("PRAGMA user_version").fetchone()
for number, script in enumerate(MIGRATIONS[current:], start=current + 1):
    with self._db:
        self._db.executescript(script)
        self._db.execute(f"PRAGMA user_version = {number}")   # append-only migrations
```

- **Thread affinity**: a `sqlite3.Connection` must stay on the thread that created it.
  `asyncio.to_thread` uses a *pool* — calls would land on random threads. Create and use the
  store on the worker's **serial lane** (`worker.serial(...)`, a one-thread executor) —
  found while building the template.
- Upserts (`ON CONFLICT … DO UPDATE`), bounded tables (keep the last N), `with db:` for
  transactions.
- One process owns the database: fzonetrack takes an exclusive `flock` on `<db>.lock` so a
  second in-process window can't corrupt it.
- Close it on shutdown on the same lane (`worker.serial(store.close).result(2)`).

## Caches

**Disk** (thumbnails, [07](07-icons-and-images.md)):
- content-addressed names: `hash(path, mtime_ns, size, variant)` → stale entries simply stop
  being hit;
- sharded dirs (`ab/abcd….webp`) to keep directories small;
- atomic writes (`mkstemp` in the same dir + `os.replace`; C++ `QSaveFile`);
- **LRU by mtime**: `os.utime(hit)` on every hit (atime is usually `relatime`/`noatime`);
- **budget**: a setting (MB); `evict()` deletes oldest-first until under budget — run it on the
  worker after bulk work, never on the GUI thread; "Clear cache" = evict with budget 0 and
  report freed bytes with `QLocale().formattedDataSize`.

**Memory**: a lock-guarded `OrderedDict` LRU of decoded `QImage`s (a few hundred) in front of
the disk cache; Qt's own pixmap cache (`Image.cache: true`) in front of that.

**HTTP**: `QNetworkDiskCache` on the `QNetworkAccessManager` (C++/Python), or the library's
cache (e.g. `hishel` for httpx) under `~/.cache/<app>/http`.

**Derived data**: cache computed results keyed by input hash in sqlite when recomputing is
expensive (scraper's cache tables); invalidate by key, never by time alone.
