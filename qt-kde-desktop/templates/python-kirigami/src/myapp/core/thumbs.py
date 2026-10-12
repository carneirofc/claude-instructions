"""Thumbnails: decode once with Pillow, store small WebP files, serve those afterwards.

Why WebP: a 256 px thumbnail is ~5-15 KB as WebP q80 against ~30-60 KB as PNG, decodes
fast in Qt (qt6-imageformats), and keeps alpha. The cache is keyed by path + mtime + size
+ edge, so an edited file gets a new thumbnail and the old one ages out of the budget.

Thread-safety: render() writes to a unique temp file and renames it into place, so any
number of image-loader threads may ask for the same thumbnail at once.
"""

from __future__ import annotations

import hashlib
import logging
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageOps

log = logging.getLogger(__name__)

# Requested edges are rounded up to these buckets: QML asks for sourceSize * devicePixelRatio,
# which varies per screen and zoom; buckets keep the hit rate high.
BUCKETS = (64, 128, 192, 256, 384, 512, 768, 1024)
WEBP = {"format": "WEBP", "quality": 80, "method": 4}  # method 0-6: speed vs size


def bucket(edge: int) -> int:
    return next((b for b in BUCKETS if b >= edge), BUCKETS[-1])


@dataclass
class ThumbnailCache:
    root: Path
    budget_bytes: int = 256 * 1024 * 1024

    def path_for(self, source: Path, edge: int) -> Path:
        stat = source.stat()
        raw = f"{source.resolve()}\0{stat.st_mtime_ns}\0{stat.st_size}\0{edge}"
        key = hashlib.blake2b(raw.encode(), digest_size=16).hexdigest()
        return self.root / key[:2] / f"{key}.webp"

    def get(self, source: Path, edge: int) -> Path | None:
        """The cached thumbnail, rendering it on a miss; None when the source can't be read."""
        edge = bucket(edge)
        try:
            target = self.path_for(source, edge)
        except OSError:
            return None
        if target.exists():
            os.utime(target)  # mtime is the LRU clock: atime is usually off (relatime/noatime)
            return target
        return target if render(source, target, edge) else None

    def evict(self) -> int:
        """Delete least-recently-used thumbnails until the cache fits its budget. Returns the
        bytes freed. Run it on the worker thread now and then, never on the GUI thread."""
        files = []
        total = 0
        for path in self.root.rglob("*.webp"):
            try:
                stat = path.stat()
            except OSError:
                continue
            files.append((stat.st_mtime, stat.st_size, path))
            total += stat.st_size
        freed = 0
        for _, size, path in sorted(files):
            if total - freed <= self.budget_bytes:
                break
            path.unlink(missing_ok=True)
            freed += size
        return freed


def render(source: Path, target: Path, edge: int) -> bool:
    try:
        with Image.open(source) as image:
            # JPEG only: decode at 1/2, 1/4 or 1/8 scale straight from the DCT; huge savings.
            image.draft("RGB", (edge, edge))
            image = ImageOps.exif_transpose(image)  # camera photos: honour the orientation tag
            image.thumbnail((edge, edge), Image.Resampling.LANCZOS)  # keeps the aspect ratio
            if image.mode not in ("RGB", "RGBA"):
                image = image.convert("RGBA" if "A" in image.getbands() else "RGB")
            target.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=target.parent, suffix=".tmp")
            with os.fdopen(fd, "wb") as out:
                image.save(out, **WEBP)
            os.replace(tmp, target)  # atomic: readers see the old file or the new one
            return True
    except (OSError, ValueError, Image.DecompressionBombError) as error:
        log.debug("no thumbnail for %s: %s", source, error)
        return False
