pragma ComponentBehavior: Bound

import QtQuick
import org.kde.kirigami as Kirigami

// A running command's output, streamed line by line; follows the tail unless scrolled up.
Kirigami.ScrollablePage {
    id: page

    readonly property QtObject browser: applicationWindow().app.browser
    readonly property QtObject runner: browser.command

    title: i18n("Command Output")
    Kirigami.Theme.colorSet: Kirigami.Theme.View
    Kirigami.Theme.inherit: false

    actions: [
        Kirigami.Action {
            text: i18n("Stop"); icon.name: "process-stop"
            visible: page.runner.running
            onTriggered: page.runner.stop()
        }
    ]

    header: Kirigami.InlineMessage {
        position: Kirigami.InlineMessage.Position.Header
        type: Kirigami.MessageType.Information
        visible: page.runner.running
        text: i18n("Running…")
    }

    ListView {
        id: lines
        objectName: "output"
        property bool following: true
        model: page.browser.outputModel
        onMovementEnded: following = atYEnd
        onCountChanged: if (following) Qt.callLater(positionViewAtEnd)
        delegate: Kirigami.SelectableLabel {
            required property string title
            required property string tone
            width: ListView.view.width
            leftPadding: Kirigami.Units.largeSpacing
            rightPadding: Kirigami.Units.largeSpacing
            text: title
            font: Kirigami.Theme.fixedWidthFont  // the user's monospace font
            wrapMode: Text.WrapAnywhere
            color: tone === "bad" ? Kirigami.Theme.negativeTextColor : Kirigami.Theme.textColor
        }

        Kirigami.PlaceholderMessage {
            anchors.centerIn: parent
            width: parent.width - Kirigami.Units.gridUnit * 4
            visible: lines.count === 0
            icon.name: "utilities-terminal"
            text: i18n("No output yet")
            explanation: i18n("Right-click a file and choose Run Command.")
        }
    }
}
