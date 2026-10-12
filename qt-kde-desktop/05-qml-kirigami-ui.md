# 05 — QML & Kirigami UI

Kirigami 6 imports: `import org.kde.kirigami as Kirigami`, `import QtQuick.Controls as
QQC2`, `import org.kde.kirigamiaddons.formcard as FormCard`,
`import org.kde.kirigami.delegates as KD`. Start delegate-bearing files with
`pragma ComponentBehavior: Bound` and use `required property` for every model role.

## Window shell

[`Main.qml`](templates/python-kirigami/src/myapp/qml/Main.qml):

```qml
Kirigami.ApplicationWindow {
    required property QtObject app
    width: app.windowWidth > 0 ? app.windowWidth : Kirigami.Units.gridUnit * 60
    minimumWidth: Kirigami.Units.gridUnit * 22
    pageStack.globalToolBar.style: Kirigami.ApplicationHeaderStyle.ToolBar
    pageStack.globalToolBar.showNavigationButtons: Kirigami.ApplicationHeaderStyle.ShowBackButton
    pageStack.columnView.columnResizeMode: wideScreen
        ? Kirigami.ColumnView.DynamicColumns : Kirigami.ColumnView.SingleColumn

    globalDrawer: Kirigami.GlobalDrawer {
        titleIcon: root.app.iconSource
        modal: !root.wideScreen                       // narrow: overlays content
        collapsible: true
        collapsed: root.width < Kirigami.Units.gridUnit * 45   // medium: icons only
        showHeaderWhenCollapsed: true
        actions: [ PageAction { name: "browser"; text: i18n("Browse"); icon.name: "folder-open" }, ... ]
    }
}
```

`component PageAction: Kirigami.Action { checkable: true; checked: root.currentPage === name }`
keeps the drawer's selection in sync.

**Navigation.** Either push `Component`s on demand (fzonetrack) or keep pages alive in a
`Kirigami.PagePool` (scraper, template — scroll position and state survive switching):

```qml
Kirigami.PagePool { id: pool }
function showPage(name) {
    const page = pool.loadPage(Qt.resolvedUrl(pageUrls[name]));
    pageStack.clear(); pageStack.push(page);
}
```

Dialog-like pages (About, settings in C++): `pageStack.pushDialogLayer(component, props)`.
kirigami-addons also has `KirigamiSettings.ConfigurationView` for multi-module settings
(fzonetrack).

## Responsive layout

Breakpoints are **gridUnit multiples**, never pixels, so they track font size and scale.

| Width | Behaviour |
| --- | --- |
| `wideScreen` (Kirigami's own threshold) | master/detail columns (`DynamicColumns`), sidebar drawer |
| `< gridUnit * 45` | drawer collapses to icons |
| `!wideScreen` | one column; drawer becomes modal; details become a pushed page |
| `< gridUnit * 22` | `minimumWidth` — below this nothing is usable |

- **Master/detail**: push the detail as a second column when there is room
  (`width >= gridUnit * 50` in scraper) and only when the list has rows; otherwise push it on
  activation. A detail page sets `Kirigami.ColumnView.fillWidth: false` and
  `Kirigami.ColumnView.preferredWidth: gridUnit * 22`.
- **Grid that fills the row** (all three apps):

  ```qml
  readonly property real cardWidth: Kirigami.Units.gridUnit * 9
  readonly property int columns: Math.max(1, Math.floor(width / cardWidth))
  cellWidth: width / columns
  cellHeight: cellWidth * 1.4 + Kirigami.Units.gridUnit * 3
  reuseItems: true
  cacheBuffer: Math.round(height)      // one screen ahead: images start loading early
  ```
- **Actions fold on narrow widths**: page `actions` with `displayHint: Kirigami.DisplayHint.IconOnly`
  or `AlwaysHide` go into the overflow menu instead of pushing the search field off-screen
  (fzonetrack). Prefer actions over custom header widgets.
- **Wrapping chips**: a `Flow` inside an `Item { implicitWidth: 0 }` so layouts don't give it
  the width of all its children (fzonetrack `TagStrip`).
- `Kirigami.Settings.isMobile`, `Kirigami.Settings.tabletMode` for touch adaptations
  (bigger targets, `FormComboBoxDelegate` switches to a dialog automatically).

## Pages

| Type | Use |
| --- | --- |
| `Kirigami.ScrollablePage` | a single scrolling thing (list, form, log) — it provides the scrollbar and pull behaviour |
| `Kirigami.Page` + `padding: 0` | custom layouts: header + grid/list `Loader` + overlays (BrowserPage) |
| `FormCard.FormCardPage` | settings, forms (`FormHeader`, `FormCard`, `FormTextFieldDelegate`, `FormSpinBoxDelegate`, `FormSwitchDelegate`, `FormComboBoxDelegate`, `FormButtonDelegate`, `FormDelegateSeparator`, `FormPasswordFieldDelegate`, `FormDateTimeDelegate`, `FormColorDelegate`) |
| `FormCard.AboutPage` | About (C++: reads KAboutData; Python: pass `aboutData` dict incl. `releases: []`) |

Page-level `header:`/`footer:` hold `InlineMessage`s, a busy line, a dirty-state toolbar
(fzonetrack `SettingsPage`: "You have unsaved changes" with Save/Revert, visible only
while dirty).

FormCard delegates and binding loops: bind `value: settings.x` and write back in
`onValueModified` / `onEditingFinished` / `onToggled` (user-initiated signals), never in
`onValueChanged`.

## Delegates

```qml
QQC2.ItemDelegate {
    required property int index
    required property string title
    highlighted: ListView.isCurrentItem          // the style draws it
    focusPolicy: Qt.NoFocus                      // the view keeps keyboard focus
    onDoubleClicked: activated()
    Accessible.name: title
    TapHandler { acceptedButtons: Qt.RightButton; onTapped: menuRequested() }
    TapHandler { acceptedDevices: PointerDevice.TouchScreen; onLongPressed: menuRequested() }
    contentItem: KD.IconTitleSubtitle { icon.name: ...; title: ...; subtitle: ...; selected: parent.highlighted }
}
```

- Tooltips only when text is elided: `QQC2.ToolTip.visible: hovered && label.truncated`.
- `elide: Text.ElideMiddle` for file names (keeps the extension).
- Kirigami 6 removed `BasicListItem` / `AbstractListItem` — use `QQC2.ItemDelegate` +
  `Kirigami.delegates` (`IconTitleSubtitle`, `TitleSubtitle`). `SwipeListItem`,
  `OverlaySheet`, `Kirigami.Dialog`, `PromptDialog`, `MenuDialog` still exist (6.30).
- **Gotcha:** a `Repeater` inside `Kirigami.FormLayout` whose model is replaced makes
  FormLayout read `Accessible` of destroyed items → TypeErrors; lay out label/value pairs
  yourself for dynamic content (scraper).

## Keyboard

- Standard keys, never hard-coded combos where one exists: `StandardKey.Open`, `Refresh`,
  `Preferences`, `Quit`, `Find`, `Save`, `Copy`.
- Actions carry shortcuts so menus show them. A *hidden* action
  (`visible: false; shortcut: StandardKey.Find`) can focus the search field.
- Page-switch shortcuts that must survive a collapsed drawer: an `Instantiator` of
  `Shortcut`s outside the drawer (scraper).
- **Conflicts:** Alt+Left/Right belong to Kirigami's page row; two enabled `Shortcut`s on
  one sequence are ambiguous and *neither* fires — gate with `enabled: page.visible`.
  `Kirigami.SearchField` claims Ctrl+F unless `focusSequences: []`.
- Esc/arrows vs text fields: guard actions with an `editingText` check on
  `activeFocusItem` (fzonetrack).
- Lists: `keyNavigationEnabled: true`, `Keys.onReturnPressed: activate(currentIndex)`,
  `Keys.onMenuPressed` for the context menu, Backspace = up.
- Focus choreography: `Qt.callLater(view.forceActiveFocus)` after showing a page; a short
  debounce before following the cursor with an expensive detail view.
- An F1 `Kirigami.Dialog` listing shortcuts (scraper `KeyboardHelp`).

## Dialogs

```qml
Kirigami.PromptDialog {                         // confirmation with icon-labelled actions
    title: i18n("Quit while working?")
    standardButtons: Kirigami.Dialog.NoButton
    customFooterActions: [
        Kirigami.Action { text: i18n("Quit"); icon.name: "application-exit"; onTriggered: ... },
        Kirigami.Action { text: i18n("Keep Working"); icon.name: "dialog-cancel"; onTriggered: close() }
    ]
}
onClosing: close => {                            // confirm quit only when work would be lost
    const blocker = quitting ? "" : app.quitBlocker();
    if (blocker !== "") { close.accepted = false; confirmQuit.subtitle = blocker; confirmQuit.open(); }
}
```

Native pickers: `QtQuick.Dialogs.FolderDialog { currentFolder: "file://" + path;
onAccepted: backend.openUrl(selectedFolder) }` — convert the URL in Python/C++
(`QUrl.toLocalFile()`), not by string slicing in QML.

## Accessibility

`Accessible.name`/`description`/`role` on delegates and icon-only buttons; icon-only
buttons keep their `text` (screen readers, tooltips): `display: QQC2.AbstractButton.IconOnly`
+ `QQC2.ToolTip.text: text`.
