"""The Qt-free core: thumbnails, storage, scanning."""

from __future__ import annotations

import os
from pathlib import Path

from PIL import Image

from myapp.core import scan
from myapp.core.store import Store
from myapp.core.thumbs import ThumbnailCache, bucket


def test_folders_come_first_and_hidden_files_stay_hidden(pictures: Path) -> None:
    (pictures / ".hidden").write_text("x")
    names = [e.name for e in scan.list_folder(pictures)]
    assert names == ["album", "logo.png", "notes.txt", "photo.jpg"]
    assert ".hidden" in [e.name for e in scan.list_folder(pictures, show_hidden=True)]


def test_thumbnails_are_small_webp_files_within_the_bucket(pictures: Path, tmp_path: Path) -> None:
    cache = ThumbnailCache(tmp_path / "thumbs")
    target = cache.get(pictures / "photo.jpg", 200)
    assert target is not None and target.suffix == ".webp"
    with Image.open(target) as image:
        assert image.format == "WEBP"
        assert max(image.size) == bucket(200) == 256
    assert target.stat().st_size < (pictures / "photo.jpg").stat().st_size
    with Image.open(cache.get(pictures / "logo.png", 128)) as image:
        assert image.mode == "RGBA"  # alpha survives


def test_an_edited_file_gets_a_new_thumbnail(pictures: Path, tmp_path: Path) -> None:
    cache = ThumbnailCache(tmp_path / "thumbs")
    photo = pictures / "photo.jpg"
    first = cache.get(photo, 128)
    os.utime(photo, ns=(0, 1_000_000_000))
    assert cache.get(photo, 128) != first


def test_unreadable_files_get_no_thumbnail(pictures: Path, tmp_path: Path) -> None:
    assert ThumbnailCache(tmp_path / "thumbs").get(pictures / "notes.txt", 128) is None


def test_eviction_drops_the_least_recently_used(pictures: Path, tmp_path: Path) -> None:
    cache = ThumbnailCache(tmp_path / "thumbs")
    old = cache.get(pictures / "photo.jpg", 512)
    new = cache.get(pictures / "logo.png", 512)
    assert old and new
    os.utime(old, (1, 1))
    cache.budget_bytes = new.stat().st_size
    assert cache.evict() > 0
    assert new.exists() and not old.exists()


def test_the_store_migrates_and_keeps_recent_folders(tmp_path: Path) -> None:
    store = Store(tmp_path / "db.sqlite")
    for name in ("a", "b", "a"):
        store.remember_folder(f"/x/{name}")
    assert store.recent_folders() == ["/x/a", "/x/b"]
    store.close()
    reopened = Store(tmp_path / "db.sqlite")  # migrations do not run twice
    assert reopened.recent_folders() == ["/x/a", "/x/b"]
    reopened.close()
