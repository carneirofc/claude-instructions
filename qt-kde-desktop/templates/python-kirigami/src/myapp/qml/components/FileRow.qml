pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.kirigami.delegates as KD

// A list row: the style draws hover/selection; Kirigami's IconTitleSubtitle lays it out.
QQC2.ItemDelegate {
    id: row

    required property int index
    required property string title
    required property string subtitle
    required property string iconName
    required property string thumbnail
    required property string badge
    required property string tone

    signal activated()
    signal menuRequested()

    highlighted: ListView.isCurrentItem
    focusPolicy: Qt.NoFocus
    onDoubleClicked: activated()
    onClicked: ListView.view.currentIndex = index
    Accessible.name: title
    Accessible.description: subtitle

    TapHandler {
        acceptedButtons: Qt.RightButton
        onTapped: { row.ListView.view.currentIndex = row.index; row.menuRequested(); }
    }

    contentItem: RowLayout {
        spacing: Kirigami.Units.largeSpacing
        KD.IconTitleSubtitle {
            Layout.fillWidth: true
            icon.name: row.iconName
            title: row.title
            subtitle: row.subtitle
            selected: row.highlighted
        }
        ToneBadge { text: row.badge; tone: row.tone }
    }
}
