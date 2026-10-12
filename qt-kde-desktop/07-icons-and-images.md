# 07 — Icons, images, thumbnails & WebP

## Theme icons

- **Names, never files**, in QML: `icon.name: "document-open-folder"`,
  `Kirigami.Icon { source: "folder-open" }`. The user's icon theme (Breeze, Papirus, …)
  draws them; Breeze is only the fallback.
- **Monochrome action icons** for actions and toolbars (`go-up`, `view-refresh`,
  `edit-copy`, `process-stop`, `configure`, `help-about`, `application-exit`,
  `view-list-details`/`view-list-icons`, `view-sort-ascending`/`-descending`,
  `dialog-warning`, `media-playback-start`). Full-colour `apps/places/mimetypes/devices`
  icons only where they *represent content* (a file's mime icon, a folder) — scraper rule.
- `-symbolic` suffixed names exist in Breeze for some icons; use them when a monochrome
  variant is wanted for a colourful base name (`applications-games-symbolic`).
- **Mime icons** from the mime database, not guessed: `QMimeDatabase().mimeTypeForFile(path,
  MatchMode.MatchExtension).iconName()` (fast: extension only; `genericIconName()` as
  fallback).
- **State in the icon**: bind it (`icon.name: running ? "process-stop" : "media-playback-start"`;
  `dialog-warning` on the log button when there are problems).
- **Semantic status icons**: `data-success`, `data-warning`, `data-error`, `data-information`.
- Sizes: `Kirigami.Units.iconSizes.small / smallMedium / medium / large / huge` only.
- **Icon-only buttons keep their text**: `display: QQC2.AbstractButton.IconOnly`,
  `text: i18n("Refresh")`, tooltip from `text` after `Kirigami.Units.toolTipDelay`,
  `Accessible.name: text`.
- Find names with the *Cuttlefish* icon browser (`plasma-sdk`), or
  `ls /usr/share/icons/breeze/actions/22`.

## The app icon

- One **SVG**, square `viewBox`, wide margin (it survives round/squircle masks — fzonetrack),
  no text, legible at 16 px, flat shapes; KDE palette blues (`#3daee9`/`#1d82c9`) are a safe
  default for a KDE-flavoured app.
- Installed as `/usr/share/icons/hicolor/scalable/apps/<APP_ID>.svg`; `Icon=<APP_ID>` in the
  `.desktop` file. pacman's `gtk-update-icon-cache` hook refreshes the cache.
- **Also ship it inside the package** (`data/icons/<APP_ID>.svg`) for source checkouts:

  ```python
  def app_icon() -> QIcon:                     # window icon
      return QIcon.fromTheme(APP_ID, QIcon(str(BUNDLED_ICON)))
  def app_icon_source() -> str:                # QML titleIcon / Kirigami.Icon source
      return APP_ID if QIcon.hasThemeIcon(APP_ID) else QUrl.fromLocalFile(str(BUNDLED_ICON)).toString()
  ```
- A Qt built elsewhere may not search `~/.local/share/icons`: append XDG data dirs to
  `QIcon.themeSearchPaths()` (template `add_xdg_icon_paths`, from scraper).

## Images in QML — the rules

```qml
Image {
    source: card.thumbnail                       // image://thumbs/<id> or a file URL
    sourceSize: Qt.size(edge * Screen.devicePixelRatio, edge * Screen.devicePixelRatio)
    fillMode: Image.PreserveAspectFit            // PreserveAspectCrop for covers
    asynchronous: true                           // decode off the GUI thread
    cache: true                                  // Qt's pixmap cache (keyed by URL + sourceSize)
    opacity: status === Image.Ready ? 1 : 0      // + Behavior → fade in
}
```

1. **Always set `sourceSize`** — otherwise a 6000×4000 photo is decoded at full size for a
   160 px cell. Multiply by `Screen.devicePixelRatio` for crisp HiDPI.
2. The pixmap cache is keyed by size: request prefetches/previews at *exactly* the displayed
   `sourceSize` or they miss (fzonetrack).
3. Placeholders: the mime/`image-missing` icon underneath, a `BusyIndicator` while
   `status === Image.Loading`, an error icon on `Image.Error`.
4. Views: `reuseItems: true`, `cacheBuffer` ≈ one screen, model only on the visible view.
5. Large galleries: load full-size pages only while the viewer is open
   (`model: viewer.opened ? pages : []`, scraper).

## Thumbnail pipeline (WebP)

```
QML Image ──image://thumbs/<b64 path>──► ThumbnailProvider.requestImage   (QML loader thread)
   sourceSize → bucket(edge)                 │ memory LRU hit? → QImage
                                             ▼
                                   ThumbnailCache.get(path, edge)           (core, no Qt)
                                     key = blake2b(path, mtime_ns, size, edge)
                                     ~/.cache/myapp/thumbnails/ab/abcd….webp exists? → touch, return
                                     else render(): Pillow decode (draft for JPEG) → EXIF
                                       transpose → thumbnail(LANCZOS) → WebP q80 → atomic rename
```

[`core/thumbs.py`](templates/python-kirigami/src/myapp/core/thumbs.py):

```python
BUCKETS = (64, 128, 192, 256, 384, 512, 768, 1024)   # requested edges round up: high hit rate
WEBP = {"format": "WEBP", "quality": 80, "method": 4}

def render(source, target, edge):
    with Image.open(source) as image:
        image.draft("RGB", (edge, edge))              # JPEG: decode at 1/2..1/8 scale from DCT
        image = ImageOps.exif_transpose(image)        # phone photos: honour orientation
        image.thumbnail((edge, edge), Image.Resampling.LANCZOS)
        if image.mode not in ("RGB", "RGBA"):
            image = image.convert("RGBA" if "A" in image.getbands() else "RGB")
        fd, tmp = tempfile.mkstemp(dir=target.parent, suffix=".tmp")
        with os.fdopen(fd, "wb") as out:
            image.save(out, **WEBP)
        os.replace(tmp, target)                       # atomic: concurrent loaders are safe
```

Why WebP: at 256 px a thumbnail is a few KB (the test asserts it is smaller than the
source), keeps alpha (PNG logos), and Qt decodes it fast. Requirements: `python-pillow`
(built with libwebp on Arch) and **`qt6-imageformats`** for Qt to read WebP — check at
startup and warn:

```python
def webp_supported() -> bool:
    return b"webp" in {bytes(f) for f in QImageReader.supportedImageFormats()}
```

Catch `OSError, ValueError, Image.DecompressionBombError` → no thumbnail (mime icon stays).
Keys include `mtime_ns` and size, so edits get new thumbnails and stale ones age out.

**Provider** ([`qt/images.py`](templates/python-kirigami/src/myapp/qt/images.py)):

```python
class ThumbnailProvider(QQuickImageProvider):
    def __init__(self, cache):
        super().__init__(QQmlImageProviderBase.ImageType.Image,
                         QQmlImageProviderBase.Flag.ForceAsynchronousImageLoading)  # never GUI thread
    def requestImage(self, image_id, size, requested):
        edge = bucket(max(requested.width(), requested.height()) if requested.isValid() else 256)
        ...  # memory LRU (lock-guarded OrderedDict of QImage) → disk cache → render
        size.setWidth(image.width()); size.setHeight(image.height())
        return image
```

- IDs are **URL-safe base64** of the path — QML URL handling would mangle `#`, `?`, `%`.
- A synchronous provider + `ForceAsynchronousImageLoading` runs on QML's loader threads:
  simplest, and fine when the work is local. For network-bound images use
  `QQuickAsyncImageProvider` with a response object (fzonetrack covers: max 6 concurrent,
  cancel drops queued work, keep the Python response alive until QML deletes it; C++
  template: a `QThreadPool` of `QRunnable` responses).
- Look in the local cache *before* any hop to another thread/loop (scraper's
  `cached_image()` fast path).

**C++ equivalent** (no Pillow): `QImageReader reader(path); reader.setAutoTransform(true);
reader.setScaledSize(full.scaled(edge, edge, Qt::KeepAspectRatio));` — Qt's JPEG plugin
then decodes at reduced scale; write with `QImageWriter(&saveFile, "webp")` +
`setQuality(80)` into a `QSaveFile` (atomic).

**Pre-warming** a folder (template `warmThumbnails`): a worker coroutine renders each image,
posts progress to the GUI thread, can be cancelled, then runs cache eviction
([09](09-async-commands-files.md), [11](11-storage-and-cache.md)).

**Alternatives worth knowing:** the freedesktop thumbnail spec cache
(`~/.cache/thumbnails/{normal,large}/<md5(uri)>.png`, shared with Dolphin) and KIO's
`KIO::PreviewJob` (C++, uses the system's thumbnailer plugins incl. video/PDF). Use them
when you want the system's thumbnails; use your own WebP cache when you control size,
format and budget.
