"""One generic list model: rows are frozen records, roles are the record's fields.

Role names are the QML ``required property`` names of the delegates, so adding a field to
``Row`` is the whole change. Rows are matched by ``key``, so the current row survives a
reload or a re-sort.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import IntEnum, auto
from typing import Any

from PySide6.QtCore import (
    QAbstractListModel,
    QByteArray,
    QModelIndex,
    QObject,
    QPersistentModelIndex,
    Qt,
    Signal,
    Slot,
)

from myapp.qt.props import qt_property

ROOT = QModelIndex()


@dataclass(frozen=True, slots=True)
class Row:
    key: str
    title: str
    subtitle: str = ""
    iconName: str = "text-x-generic"  # a theme icon name, never a file
    thumbnail: str = ""  # an image:// URL, or "" for none
    tone: str = "neutral"  # neutral | accent | good | warn | bad, see ToneBadge.qml
    badge: str = ""
    isFolder: bool = False


class Role(IntEnum):
    key = Qt.ItemDataRole.UserRole + 1
    title = auto()
    subtitle = auto()
    iconName = auto()
    thumbnail = auto()
    tone = auto()
    badge = auto()
    isFolder = auto()


class RowsModel(QAbstractListModel):
    countChanged = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._rows: list[Row] = []
        for signal in (self.modelReset, self.rowsInserted, self.rowsRemoved):
            signal.connect(self.countChanged)

    def rowCount(self, parent: QModelIndex | QPersistentModelIndex = ROOT) -> int:
        return 0 if parent.isValid() else len(self._rows)

    def roleNames(self) -> dict[int, QByteArray]:
        return {role.value: QByteArray(role.name.encode()) for role in Role}

    def data(self, index: QModelIndex | QPersistentModelIndex,
             role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or not 0 <= index.row() < len(self._rows):
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            role = Role.title
        try:
            return getattr(self._rows[index.row()], Role(role).name)
        except ValueError:
            return None

    def rows(self) -> list[Row]:
        return list(self._rows)

    def set_rows(self, rows: list[Row]) -> None:
        """Whole-list replace. For a sort use layoutAboutToBeChanged/layoutChanged instead,
        and for one row's change, update(): delegates then stay alive and animate."""
        self.beginResetModel()
        self._rows = list(rows)
        self.endResetModel()

    def update(self, key: str, **changes: Any) -> None:
        for position, row in enumerate(self._rows):
            if row.key == key:
                self._rows[position] = replace(row, **changes)
                index = self.index(position)
                roles = [Role[name].value for name in changes]
                self.dataChanged.emit(index, index, roles)
                return

    @Slot(int, result=str)
    def keyAt(self, position: int) -> str:
        return self._rows[position].key if 0 <= position < len(self._rows) else ""

    def _count(self) -> int:
        return len(self._rows)

    count = qt_property(_count, int, notify=countChanged)
