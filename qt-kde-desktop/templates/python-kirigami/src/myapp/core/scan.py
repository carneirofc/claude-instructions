"""List a folder: blocking I/O, so it runs on the worker thread, never on the GUI thread."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# Formats the thumbnailer (Pillow) decodes; anything else gets a mime-type icon.
IMAGE_SUFFIXES = frozenset({".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tif", ".tiff"})


@dataclass(frozen=True, slots=True)
class Entry:
    path: str
    name: str
    is_dir: bool
    size: int
    mtime: float

    @property
    def is_image(self) -> bool:
        return not self.is_dir and Path(self.name).suffix.lower() in IMAGE_SUFFIXES


def list_folder(folder: Path, *, show_hidden: bool = False) -> list[Entry]:
    """Folders first, then files, each by name (case-insensitive, like Dolphin)."""
    entries: list[Entry] = []
    with os.scandir(folder) as found:
        for item in found:
            if not show_hidden and item.name.startswith("."):
                continue
            try:
                stat = item.stat()
                is_dir = item.is_dir()
            except OSError:  # a dangling link, or removed meanwhile
                continue
            entries.append(Entry(item.path, item.name, is_dir, stat.st_size, stat.st_mtime))
    entries.sort(key=lambda e: (not e.is_dir, e.name.casefold()))
    return entries
