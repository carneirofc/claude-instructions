"""Where things live, by the XDG base directory spec (platformdirs reads $XDG_*_HOME).

    config  ~/.config/myapprc              user choices (KConfig-compatible name; QSettings ini)
    state   ~/.local/state/myapp/          window size, last folder, logs: lose it, lose nothing
    cache   ~/.cache/myapp/                thumbnails: deletable at any time, size-budgeted
    data    ~/.local/share/myapp/          the database: the user's data, never auto-deleted
"""

from __future__ import annotations

from pathlib import Path

from platformdirs import user_cache_path, user_config_path, user_data_path, user_state_path

from myapp import APP_NAME


def config_file() -> Path:
    return user_config_path() / f"{APP_NAME}rc"


def state_dir() -> Path:
    return _made(user_state_path(APP_NAME))


def cache_dir() -> Path:
    return _made(user_cache_path(APP_NAME))


def data_dir() -> Path:
    return _made(user_data_path(APP_NAME))


def _made(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path
