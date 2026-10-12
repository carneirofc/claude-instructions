pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Dialogs as Dialogs
import org.kde.kirigami as Kirigami
import org.kde.kirigami.delegates as KD
import io.github.example.myapp

Kirigami.ScrollablePage {
    id: page

    title: Backend.title
    Kirigami.Theme.colorSet: Kirigami.Theme.View
    Kirigami.Theme.inherit: false

    actions: [
        Kirigami.Action { text: i18n("Up"); icon.name: "go-up"; shortcut: "Alt+Up"
                          displayHint: Kirigami.DisplayHint.IconOnly; onTriggered: Backend.up() },
        Kirigami.Action { text: i18n("Open Folder…"); icon.name: "document-open-folder"
                          shortcut: StandardKey.Open; onTriggered: folderDialog.open() }
    ]

    Dialogs.FolderDialog {
        id: folderDialog
        currentFolder: "file://" + Backend.folderPath
        onAccepted: Backend.openUrl(selectedFolder)
    }

    GridView {
        id: grid
        readonly property real cardWidth: Config.thumbnailSize + Kirigami.Units.largeSpacing * 2
        readonly property int columns: Math.max(1, Math.floor(width / cardWidth))
        model: Backend.folder
        cellWidth: width / columns
        cellHeight: Config.thumbnailSize + Kirigami.Units.gridUnit * 3
        reuseItems: true
        cacheBuffer: Math.round(height)
        keyNavigationEnabled: true

        delegate: QQC2.ItemDelegate {
            id: cell
            required property int index
            required property string title
            required property string iconName
            required property string thumbnail
            width: GridView.view.cellWidth
            height: GridView.view.cellHeight
            highlighted: GridView.isCurrentItem
            onDoubleClicked: Backend.activate(index)
            Accessible.name: title

            contentItem: Column {
                spacing: Kirigami.Units.smallSpacing
                Item {
                    width: parent.width
                    height: Config.thumbnailSize
                    Kirigami.Icon {
                        anchors.centerIn: parent
                        width: Kirigami.Units.iconSizes.huge; height: width
                        source: cell.iconName
                        visible: thumb.status !== Image.Ready
                    }
                    Image {
                        id: thumb
                        anchors.fill: parent
                        source: cell.thumbnail
                        sourceSize: Qt.size(Config.thumbnailSize * Screen.devicePixelRatio,
                                            Config.thumbnailSize * Screen.devicePixelRatio)
                        fillMode: Image.PreserveAspectFit
                        asynchronous: true
                        opacity: status === Image.Ready ? 1 : 0
                        Behavior on opacity { NumberAnimation { duration: Kirigami.Units.longDuration } }
                    }
                }
                QQC2.Label {
                    width: parent.width
                    text: cell.title
                    elide: Text.ElideMiddle
                    horizontalAlignment: Text.AlignHCenter
                }
            }
        }

        Kirigami.PlaceholderMessage {
            anchors.centerIn: parent
            width: parent.width - Kirigami.Units.gridUnit * 4
            visible: grid.count === 0 && !Backend.busy
            icon.name: "folder-open"
            text: i18n("This folder is empty")
        }
    }
}
