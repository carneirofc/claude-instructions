"""``image://thumbs/<id>``: thumbnails for QML, rendered and cached by core.thumbs.

ForceAsynchronousImageLoading makes Qt call requestImage on its image-loader threads,
never on the GUI thread, so a cache miss (a Pillow decode) cannot stall the window. QML
must pin ``sourceSize``: that is the ``requested`` size here, and the cache bucket.

A small in-memory LRU of decoded QImages sits in front of the disk cache, so scrolling
back up does not even decode WebP again. QImage is safe to share across threads.
"""

from __future__ import annotations

import base64
import threading
from collections import OrderedDict
from pathlib import Path

from PySide6.QtCore import QSize
from PySide6.QtGui import QImage, QImageReader
from PySide6.QtQml import QQmlImageProviderBase
from PySide6.QtQuick import QQuickImageProvider

from myapp.core.thumbs import ThumbnailCache, bucket

PROVIDER = "thumbs"
DEFAULT_EDGE = 256
MEMORY_ITEMS = 300


def thumbnail_url(path: str) -> str:
    """URL-safe base64: a path may hold any byte QML's URL handling would mangle."""
    return f"image://{PROVIDER}/" + base64.urlsafe_b64encode(path.encode()).decode()


def webp_supported() -> bool:
    """Qt decodes WebP through qt6-imageformats; without it, thumbnails stay blank."""
    return b"webp" in {bytes(f) for f in QImageReader.supportedImageFormats()}


class ThumbnailProvider(QQuickImageProvider):
    def __init__(self, cache: ThumbnailCache) -> None:
        super().__init__(
            QQmlImageProviderBase.ImageType.Image,
            QQmlImageProviderBase.Flag.ForceAsynchronousImageLoading,
        )
        self._cache = cache
        self._memory: OrderedDict[tuple[str, int], QImage] = OrderedDict()
        self._lock = threading.Lock()

    def requestImage(self, image_id: str, size: QSize, requested: QSize) -> QImage:
        edge = bucket(max(requested.width(), requested.height()) if requested.isValid()
                      else DEFAULT_EDGE)
        key = (image_id, edge)
        with self._lock:
            if (hit := self._memory.get(key)) is not None:
                self._memory.move_to_end(key)
                return self._sized(hit, size)
        path = Path(base64.urlsafe_b64decode(image_id.encode()).decode())
        target = self._cache.get(path, edge)
        image = QImage(str(target)) if target else QImage()
        if not image.isNull():
            with self._lock:
                self._memory[key] = image
                while len(self._memory) > MEMORY_ITEMS:
                    self._memory.popitem(last=False)
        return self._sized(image, size)

    @staticmethod
    def _sized(image: QImage, size: QSize) -> QImage:
        size.setWidth(image.width())
        size.setHeight(image.height())
        return image
