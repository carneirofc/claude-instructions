pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Dialogs as Dialogs
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import "../components"

// A folder of files as a responsive grid of thumbnails, or a list.
Kirigami.Page {
    id: page

    readonly property QtObject app: applicationWindow().app
    readonly property QtObject browser: app.browser
    readonly property QtObject settings: app.settings
    readonly property bool hasRows: browser.model.count > 0
    property bool gridMode: true

    title: browser.title
    padding: 0
    // The content area is a "view" surface (lighter in Breeze), like Dolphin's.
    Kirigami.Theme.colorSet: Kirigami.Theme.View
    Kirigami.Theme.inherit: false

    actions: [
        Kirigami.Action {
            text: i18n("Up"); icon.name: "go-up"
            enabled: page.browser.canGoUp
            shortcut: "Alt+Up"
            displayHint: Kirigami.DisplayHint.IconOnly
            onTriggered: page.browser.up()
        },
        Kirigami.Action {
            text: i18n("Open Folder…"); icon.name: "document-open-folder"
            shortcut: StandardKey.Open
            onTriggered: folderDialog.open()
        },
        Kirigami.Action {
            text: page.gridMode ? i18n("Show as List") : i18n("Show as Grid")
            icon.name: page.gridMode ? "view-list-details" : "view-list-icons"
            displayHint: Kirigami.DisplayHint.IconOnly
            onTriggered: page.gridMode = !page.gridMode
        },
        Kirigami.Action {
            text: i18n("Prepare Thumbnails"); icon.name: "view-preview"
            enabled: page.browser.progress < 0
            displayHint: Kirigami.DisplayHint.AlwaysHide
            onTriggered: page.browser.warmThumbnails()
        },
        Kirigami.Action {
            text: i18n("Refresh"); icon.name: "view-refresh"
            shortcut: StandardKey.Refresh
            displayHint: Kirigami.DisplayHint.AlwaysHide
            onTriggered: page.browser.reload()
        }
    ]

    // The platform's folder picker: Dolphin's dialog on Plasma (plasma-integration), the
    // portal's elsewhere (xdg-desktop-portal). Never a custom one.
    Dialogs.FolderDialog {
        id: folderDialog
        title: i18n("Open Folder")
        currentFolder: "file://" + page.browser.folder
        onAccepted: page.browser.openUrl(selectedFolder)
    }

    header: ColumnLayout {
        spacing: 0
        BusyLine { Layout.fillWidth: true; busy: page.browser.busy }
        Kirigami.InlineMessage {
            Layout.fillWidth: true
            position: Kirigami.InlineMessage.Position.Header
            type: Kirigami.MessageType.Information
            visible: page.browser.progress >= 0
            text: i18n("Preparing thumbnails… %1%", Math.round(page.browser.progress * 100))
            actions: Kirigami.Action {
                text: i18n("Stop"); icon.name: "process-stop"
                onTriggered: page.browser.cancelWarm()
            }
        }
        QQC2.ProgressBar {
            Layout.fillWidth: true
            visible: page.browser.progress >= 0
            value: Math.max(0, page.browser.progress)
        }
    }

    Loader {
        id: viewLoader
        anchors.fill: parent
        sourceComponent: page.gridMode ? gridComponent : listComponent
        // A gentle cross-fade when switching grid/list.
        onLoaded: { item.opacity = 0; fade.restart(); }
        OpacityAnimator { id: fade; target: viewLoader.item as Item; from: 0; to: 1
                          duration: Kirigami.Units.longDuration; easing.type: Easing.OutCubic }
    }

    Component {
        id: gridComponent
        QQC2.ScrollView {
            GridView {
                id: grid
                objectName: "grid"
                // Columns fill the width exactly: as many cards of at least cardWidth as fit.
                readonly property real cardWidth: page.settings.thumbnailSize + Kirigami.Units.largeSpacing * 2
                readonly property int columns: Math.max(1, Math.floor(width / cardWidth))
                model: page.browser.model
                cellWidth: width / columns
                cellHeight: page.settings.thumbnailSize + Kirigami.Units.gridUnit * 3
                reuseItems: true
                cacheBuffer: Math.round(height)  // a screen ahead: thumbnails load before you scroll
                keyNavigationEnabled: true
                currentIndex: -1
                populate: Transition { NumberAnimation { properties: "opacity"; from: 0; to: 1
                                       duration: Kirigami.Units.longDuration } }
                delegate: FileCard {
                    width: GridView.view.cellWidth
                    height: GridView.view.cellHeight
                    edge: page.settings.thumbnailSize
                    onActivated: page.browser.activate(index)
                    onMenuRequested: rowMenu.popupFor(index)
                }
                Keys.onReturnPressed: page.browser.activate(currentIndex)
                Keys.onMenuPressed: rowMenu.popupFor(currentIndex)
                Keys.onPressed: event => {
                    if (event.key === Qt.Key_Backspace) { page.browser.up(); event.accepted = true; }
                }
            }
        }
    }

    Component {
        id: listComponent
        QQC2.ScrollView {
            ListView {
                objectName: "list"
                model: page.browser.model
                reuseItems: true
                keyNavigationEnabled: true
                currentIndex: -1
                add: Transition { NumberAnimation { properties: "opacity"; from: 0; to: 1
                                  duration: Kirigami.Units.shortDuration } }
                delegate: FileRow {
                    width: ListView.view.width
                    onActivated: page.browser.activate(index)
                    onMenuRequested: rowMenu.popupFor(index)
                }
                Keys.onReturnPressed: page.browser.activate(currentIndex)
                Keys.onMenuPressed: rowMenu.popupFor(currentIndex)
            }
        }
    }

    QQC2.Menu {
        id: rowMenu
        property int row: -1
        function popupFor(index: int): void { if (index >= 0) { row = index; popup(); } }
        QQC2.MenuItem { text: i18n("Open"); icon.name: "document-open"
                        onTriggered: page.browser.activate(rowMenu.row) }
        QQC2.MenuItem { text: i18n("Show in File Manager"); icon.name: "system-file-manager"
                        onTriggered: page.browser.reveal(rowMenu.row) }
        QQC2.MenuItem { text: i18n("Copy Path"); icon.name: "edit-copy"
                        onTriggered: page.browser.copyPath(rowMenu.row) }
        QQC2.MenuSeparator {}
        QQC2.MenuItem { text: i18n("Run Command"); icon.name: "utilities-terminal"
                        enabled: !page.browser.command.running
                        onTriggered: { page.browser.runCommand(rowMenu.row); applicationWindow().showPage("output"); } }
    }

    Kirigami.PlaceholderMessage {
        anchors.centerIn: parent
        width: parent.width - Kirigami.Units.gridUnit * 4
        visible: !page.hasRows && !page.browser.busy
        icon.name: page.browser.empty.icon
        text: page.browser.empty.title
        explanation: page.browser.empty.hint
        helpfulAction: Kirigami.Action {
            text: i18n("Open Folder…"); icon.name: "document-open-folder"
            onTriggered: folderDialog.open()
        }
    }

    // Drop a folder (or a file: its folder) from Dolphin or the desktop.
    DropArea {
        id: drop
        anchors.fill: parent
        keys: ["text/uri-list"]
        onDropped: drop => { if (drop.hasUrls) page.browser.openUrl(drop.urls[0]) }
        Rectangle {
            anchors.fill: parent
            color: Kirigami.ColorUtils.tintWithAlpha(Kirigami.Theme.backgroundColor, Kirigami.Theme.highlightColor, 0.15)
            border.color: Kirigami.Theme.highlightColor
            border.width: Math.max(1, Math.round(Kirigami.Units.smallSpacing / 2))
            radius: Kirigami.Units.cornerRadius
            opacity: drop.containsDrag ? 1 : 0
            visible: opacity > 0
            Behavior on opacity { OpacityAnimator { duration: Kirigami.Units.shortDuration } }
        }
    }
}
