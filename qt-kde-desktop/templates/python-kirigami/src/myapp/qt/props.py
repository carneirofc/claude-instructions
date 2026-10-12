"""A typed one-liner for read-only Qt properties.

    def _count(self) -> int: return len(self._rows)
    count = qt_property(_count, int, notify=countChanged)

Without ``notify`` the property is ``constant``. The cast makes type checkers see the
getter's return type instead of a ``Property`` descriptor.

PySide6 gotcha: a Property whose ``notify`` signal is declared on a *base* class crashes.
Declare such properties on the base class itself and let subclasses override a hook.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

from PySide6.QtCore import Property, Signal


def qt_property[S, T](
    getter: Callable[[S], T], kind: type | str, *, notify: Signal | None = None
) -> T:
    if notify is None:
        return cast("T", Property(kind, getter, constant=True))
    return cast("T", Property(kind, getter, notify=notify))
