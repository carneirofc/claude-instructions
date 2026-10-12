# 12 — Desktop integration

## One id to rule them all

`APP_ID = "io.github.<user>.<app>"` (reverse-DNS you control). It must be identical in:

| Place | Value |
| --- | --- |
| `.desktop` file name | `/usr/share/applications/<APP_ID>.desktop` |
| `Icon=` and the icon file | `/usr/share/icons/hicolor/scalable/apps/<APP_ID>.svg` |
| `StartupWMClass=` | `<APP_ID>` (X11 matching; Wayland uses the app id) |
| Qt | `QGuiApplication.setDesktopFileName(APP_ID)` / `KAboutData.setDesktopFileName` |
| AppStream | `<id>` and `<launchable type="desktop-id"><APP_ID>.desktop` |
| D-Bus | session bus name for single instance |
| notifyrc | `DesktopEntry=<APP_ID>` |

The *component name* (`APP_NAME = "myapp"`) names the notifyrc, the config file
(`myapprc`), the gettext domain and `QCoreApplication.applicationName`.

On Wayland the compositor and the portal identify the window **only** by
`desktopFileName`: without a matching installed `.desktop`, Plasma shows a generic icon,
can't pin it, and portals refuse to register the app id. For runs from a source checkout,
fzonetrack writes a hidden user entry at startup — marked so it never overwrites a real one,
and removed when an installed entry exists (a user-level file shadows `/usr/share`):

```python
DESKTOP_ENTRY_MARKER = "# Written by fzonetrack-qt on start"
# NoDisplay=true, Exec=<this interpreter + module>, Icon=<bundled svg path>
```

## .desktop

[`packaging/arch/<id>.desktop`](templates/python-kirigami/packaging/arch/io.github.example.myapp.desktop):

```ini
[Desktop Entry]
Type=Application
Version=1.5
Name=My App
Name[pt_BR]=Meu App
GenericName=Image Browser
Comment=Browse image folders with a native look
Exec=myapp %f                   # %f/%F/%u/%U when it takes files/URLs
TryExec=myapp                   # hides the entry if the binary is gone
Icon=io.github.example.myapp
Terminal=false
StartupNotify=true
StartupWMClass=io.github.example.myapp
Categories=Qt;KDE;Graphics;Viewer;
MimeType=inode/directory;       # appears in "Open with"
Keywords=image;photo;thumbnail;folder;
```

Validate: `desktop-file-validate` (in `check()`). User-local installs rewrite
`Exec`/`TryExec` to absolute venv paths with `sed` and run `update-desktop-database
~/.local/share/applications` themselves (no pacman hook watches `~/.local`).

## AppStream metainfo

`/usr/share/metainfo/<APP_ID>.metainfo.xml` — what Discover shows. Minimum:
`id`, `metadata_license` (CC0-1.0), `project_license`, `name`, `summary`, `description`,
`launchable`, `developer`, `url homepage/bugtracker`, `provides/binary`,
`content_rating`, `releases`. Add `screenshots` for software centres. Validate with
`appstreamcli validate --no-net` (`checkdepends=appstream`). **XML comments cannot contain
`--`** — writing `--no-net` inside a comment fails validation (hit while building the
template).

## Notifications: notifyrc

`/usr/share/knotifications6/<APP_NAME>.notifyrc`:

```ini
[Global]
IconName=io.github.example.myapp
Comment=My App
DesktopEntry=io.github.example.myapp

[Event/thumbnailsReady]
Name=Thumbnails ready
Comment=Thumbnails finished preparing while the window was in the background
Action=Popup

[Event/taskFailed]
Name=Task failed
Action=Popup
Urgency=High
```

KNotifications fires only events it finds in `$XDG_DATA_DIRS/knotifications6/`. For source
checkouts prepend the bundled `data/` dir to `XDG_DATA_DIRS` **before the first
notification** (template `expose_notifyrc()`, from fzonetrack). Event ids in code must
match `[Event/<id>]`. Users configure sound/popup per event in System Settings.

## Single instance

Python (no KDBusService binding):

```python
bus = QDBusConnection.sessionBus()
if bus.isConnected() and not bus.registerService(APP_ID):
    QDBusInterface(APP_ID, "/", f"{APP_ID}.App", bus).call("activate"); return 0

@ClassInfo({"D-Bus Interface": f"{APP_ID}.App"})
class AppAdaptor(QObject):
    @Slot()
    def activate(self): self._window.show(); self._window.raise_(); self._window.requestActivate()
bus.registerObject("/", AppAdaptor(window), QDBusConnection.RegisterOption.ExportAllSlots)
```

C++: `KDBusService service(KDBusService::Unique);` + `activateRequested` → raise. Pass
arguments (a folder to open) through the activation call if the app takes them.

## System tray (only if the app runs in the background)

```python
from KStatusNotifierItem import KStatusNotifierItem       # pacman: kstatusnotifieritem
sni = KStatusNotifierItem(APP_NAME, parent)
sni.setCategory(KStatusNotifierItem.ItemCategory.ApplicationStatus)
sni.setStatus(KStatusNotifierItem.ItemStatus.Active)
sni.setIconByName(APP_ID)                                  # theme icon; setIconByPixmap fallback
sni.setAssociatedWindow(window)                            # click toggles the window
sni.setContextMenu(menu)                                   # QMenu with theme-icon QActions
sni.setToolTip(APP_ID, title, status_text)                 # coalesce updates with a 0 ms single-shot timer
```

Fallback `QSystemTrayIcon`; no tray at all → closing quits. Close-to-tray:
`app.setQuitOnLastWindowClosed(False)` + an event filter turning `Close` into `hide()`
while a "Keep running in the tray" preference (default on) is set (fzonetrack).

## Other freedesktop/KDE services

| Need | Service |
| --- | --- |
| Reveal a file | `org.freedesktop.FileManager1.ShowItems/ShowFolders` |
| Default app / URL | `QDesktopServices.openUrl` (portal-aware) |
| File dialogs | `QtQuick.Dialogs` → plasma-integration (Dolphin dialog) / xdg-desktop-portal |
| Inhibit sleep during long work | `org.freedesktop.portal.Inhibit` or `org.freedesktop.PowerManagement.Inhibit` |
| Job progress in Plasma's notification area | KIO jobs / `KUiServerV2JobTracker` (C++) |
| Background service | a systemd **user** unit; the UI probes it and starts it through the same entry point (fzonetrack) |
| Autostart | `~/.config/autostart/<APP_ID>.desktop` (per-user, opt-in from settings) |
| Global shortcuts | KGlobalAccel (C++) / the GlobalShortcuts portal |

## Logging on a Plasma session

Qt warnings and QML `console.*` from apps started from the menu go to the journal or
nowhere: install `qInstallMessageHandler` → Python logging → a file under
`~/.local/state/<app>/`, and show it in an in-app Log page ([08](08-user-feedback.md)).
