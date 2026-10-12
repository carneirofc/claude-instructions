pragma ComponentBehavior: Bound

import QtQuick
import org.kde.kirigami as Kirigami
import io.github.example.myapp

// Same shell as the Python template: in C++ the backend is a registered singleton
// (Backend, Config) instead of an initial property, and i18n() is real KI18n.
Kirigami.ApplicationWindow {
    id: root

    title: i18n("My App")
    width: Kirigami.Units.gridUnit * 60
    height: Kirigami.Units.gridUnit * 40
    minimumWidth: Kirigami.Units.gridUnit * 22

    pageStack.globalToolBar.style: Kirigami.ApplicationHeaderStyle.ToolBar
    pageStack.initialPage: BrowserPage {}

    globalDrawer: Kirigami.GlobalDrawer {
        title: i18n("My App")
        titleIcon: "io.github.example.myapp"
        modal: !root.wideScreen
        collapsible: true
        collapsed: root.width < Kirigami.Units.gridUnit * 45
        showHeaderWhenCollapsed: true
        actions: [
            Kirigami.Action {
                text: i18n("Settings"); icon.name: "configure"; shortcut: StandardKey.Preferences
                onTriggered: root.pageStack.pushDialogLayer(Qt.resolvedUrl("SettingsPage.qml"))
            },
            Kirigami.Action {
                text: i18n("About My App"); icon.name: "help-about"
                // No aboutData needed: AboutPage reads KAboutData::applicationData().
                onTriggered: root.pageStack.pushDialogLayer(
                    Qt.createComponent("org.kde.kirigamiaddons.formcard", "AboutPage"))
            },
            Kirigami.Action {
                text: i18n("Quit"); icon.name: "application-exit"; shortcut: StandardKey.Quit
                onTriggered: Qt.quit()
            }
        ]
    }

    Connections {
        target: Backend
        function onMessage(text: string): void { root.showPassiveNotification(text) }
        function onProblem(text: string): void { root.showPassiveNotification(text, "long") }
    }
}
