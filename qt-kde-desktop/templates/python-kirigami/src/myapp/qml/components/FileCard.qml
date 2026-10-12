pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

// A grid cell: thumbnail (fades in when decoded), mime icon until then, title, badge.
QQC2.ItemDelegate {
    id: card

    required property int index
    required property string title
    required property string subtitle
    required property string iconName
    required property string thumbnail
    required property string badge
    required property string tone
    property int edge: Kirigami.Units.gridUnit * 8

    signal activated()
    signal menuRequested()

    highlighted: GridView.isCurrentItem
    focusPolicy: Qt.NoFocus
    padding: Kirigami.Units.smallSpacing
    onDoubleClicked: activated()
    onClicked: GridView.view.currentIndex = index
    Accessible.name: title
    Accessible.description: subtitle

    TapHandler {
        acceptedButtons: Qt.RightButton
        onTapped: { card.GridView.view.currentIndex = card.index; card.menuRequested(); }
    }
    TapHandler {  // touch: long-press opens the menu
        acceptedDevices: PointerDevice.TouchScreen
        onLongPressed: card.menuRequested()
    }

    contentItem: ColumnLayout {
        spacing: Kirigami.Units.smallSpacing

        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: card.edge
            clip: true

            Kirigami.Icon {
                anchors.centerIn: parent
                width: Kirigami.Units.iconSizes.huge
                height: width
                source: card.iconName
                visible: thumb.status !== Image.Ready
                opacity: card.thumbnail !== "" ? 0.4 : 1
            }
            Image {
                id: thumb
                anchors.fill: parent
                source: card.thumbnail
                // The provider renders at this size: device pixels, so HiDPI stays sharp.
                sourceSize: Qt.size(card.edge * Screen.devicePixelRatio, card.edge * Screen.devicePixelRatio)
                fillMode: Image.PreserveAspectFit
                asynchronous: true
                cache: true  // Qt's pixmap cache, keyed by URL + sourceSize
                opacity: status === Image.Ready ? 1 : 0
                scale: card.hovered ? 1.04 : 1
                Behavior on opacity { NumberAnimation { duration: Kirigami.Units.longDuration; easing.type: Easing.OutCubic } }
                Behavior on scale { ScaleAnimator { duration: Kirigami.Units.shortDuration; easing.type: Easing.OutCubic } }
            }
            QQC2.BusyIndicator {
                anchors.centerIn: parent
                running: thumb.status === Image.Loading
                visible: running
            }
            ToneBadge {
                anchors { right: parent.right; bottom: parent.bottom; margins: Kirigami.Units.smallSpacing }
                text: card.badge
                tone: card.tone
            }
        }
        QQC2.Label {
            id: label
            Layout.fillWidth: true
            text: card.title
            elide: Text.ElideMiddle  // keeps the extension visible, like Dolphin
            horizontalAlignment: Text.AlignHCenter
            QQC2.ToolTip.visible: card.hovered && truncated
            QQC2.ToolTip.text: card.title
            QQC2.ToolTip.delay: Kirigami.Units.toolTipDelay
        }
    }
}
