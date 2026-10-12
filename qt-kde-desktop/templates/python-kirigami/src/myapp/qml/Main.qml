pragma ComponentBehavior: Bound

import QtQuick
import org.kde.kirigami as Kirigami

// The window shell: navigation, toasts, quit confirmation. Pages own their content.
// No colour, pixel size or duration literal anywhere: Kirigami.Theme and Kirigami.Units
// carry the user's colour scheme, fonts, icon theme, scale and animation speed.
Kirigami.ApplicationWindow {
    id: root

    required property QtObject app
    property string currentPage: ""
    property bool quitting: false

    readonly property var pageUrls: ({
        "browser": "pages/BrowserPage.qml",
        "output": "pages/OutputPage.qml",
        "settings": "pages/SettingsPage.qml"
    })

    title: i18n("My App")
    width: app.windowWidth > 0 ? app.windowWidth : Kirigami.Units.gridUnit * 60
    height: app.windowHeight > 0 ? app.windowHeight : Kirigami.Units.gridUnit * 40
    minimumWidth: Kirigami.Units.gridUnit * 22
    minimumHeight: Kirigami.Units.gridUnit * 20

    pageStack.globalToolBar.style: Kirigami.ApplicationHeaderStyle.ToolBar
    pageStack.globalToolBar.showNavigationButtons: Kirigami.ApplicationHeaderStyle.ShowBackButton
    pageStack.columnView.columnResizeMode: wideScreen
        ? Kirigami.ColumnView.DynamicColumns : Kirigami.ColumnView.SingleColumn

    // Pages are created once and kept: their scroll position and state survive switching.
    Kirigami.PagePool { id: pool }

    function showPage(name: string): void {
        const page = pool.loadPage(Qt.resolvedUrl(pageUrls[name]));
        if (pageStack.currentItem === page)
            return;
        pageStack.clear();
        pageStack.push(page);
        currentPage = name;
        pageEnter.page = page;
        pageEnter.restart();
    }

    function showAbout(): void {
        pageStack.pushDialogLayer(Qt.createComponent("org.kde.kirigamiaddons.formcard", "AboutPage"),
                                  { aboutData: app.aboutData });
    }

    Component.onCompleted: showPage("browser")

    // One shared enter animation, retargeted per page. If it is cut short (a fast page
    // switch), onStopped puts the page back to fully visible.
    ParallelAnimation {
        id: pageEnter
        property Item page
        NumberAnimation { target: pageEnter.page; property: "opacity"; from: 0; to: 1
                          duration: Kirigami.Units.longDuration; easing.type: Easing.OutCubic }
        NumberAnimation { target: pageEnter.page; property: "scale"; from: 0.98; to: 1
                          duration: Kirigami.Units.longDuration; easing.type: Easing.OutCubic }
        onStopped: if (page) { page.opacity = 1; page.scale = 1; }
    }

    component PageAction: Kirigami.Action {
        required property string name
        checkable: true
        checked: root.currentPage === name
        onTriggered: root.showPage(name)
    }

    // Wide: a sidebar. Medium: icons only. Narrow: a hamburger menu over the content.
    globalDrawer: Kirigami.GlobalDrawer {
        title: i18n("My App")
        titleIcon: root.app.iconSource
        isMenu: !root.wideScreen && Kirigami.Settings.isMobile
        modal: !root.wideScreen
        collapsible: true
        collapsed: root.width < Kirigami.Units.gridUnit * 45
        showHeaderWhenCollapsed: true
        actions: [
            PageAction { name: "browser"; text: i18n("Browse"); icon.name: "folder-open" },
            PageAction { name: "output"; text: i18n("Command Output"); icon.name: "utilities-terminal" },
            PageAction { name: "settings"; text: i18n("Settings"); icon.name: "configure"
                         shortcut: StandardKey.Preferences },
            Kirigami.Action { separator: true },
            Kirigami.Action { text: i18n("About My App"); icon.name: "help-about"
                              onTriggered: root.showAbout() },
            Kirigami.Action { text: i18n("Quit"); icon.name: "application-exit"
                              shortcut: StandardKey.Quit; onTriggered: root.close() }
        ]
    }

    // Controllers speak; the window shows. Errors stay longer.
    Connections {
        target: root.app
        function onMessage(text: string): void { root.showPassiveNotification(text) }
        function onProblem(text: string): void { root.showPassiveNotification(text, "long") }
    }

    Kirigami.PromptDialog {
        id: confirmQuit
        title: i18n("Quit while working?")
        standardButtons: Kirigami.Dialog.NoButton
        customFooterActions: [
            Kirigami.Action {
                text: i18n("Quit"); icon.name: "application-exit"
                onTriggered: { root.quitting = true; root.close() }
            },
            Kirigami.Action {
                text: i18n("Keep Working"); icon.name: "dialog-cancel"
                onTriggered: confirmQuit.close()
            }
        ]
    }

    onClosing: close => {
        const blocker = quitting ? "" : app.quitBlocker();
        if (blocker !== "") {
            close.accepted = false;
            confirmQuit.subtitle = blocker;
            confirmQuit.open();
            return;
        }
        app.saveWindow(width, height);
    }
}
