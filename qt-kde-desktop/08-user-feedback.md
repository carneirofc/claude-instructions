# 08 — User feedback

## The ladder

Pick the lightest level that fits; never a modal for something a toast can say.

| Situation | Pattern | Lifetime |
| --- | --- | --- |
| A confirmation ("Copied …", "Saved") | toast: `showPassiveNotification(text)` | short |
| An error the user should notice | toast `"long"` + an action ("Show log", "Retry") | long |
| A state of the page (offline, failed load, restart needed, paused) | `Kirigami.InlineMessage` in the page header | while true |
| An invalid field | `statusMessage` + `status` on the FormCard delegate | until fixed |
| Loading a list | `BusyLine` (indeterminate bar, opacity only) | while busy |
| First load, nothing yet | `Kirigami.LoadingPlaceholder` | until loaded |
| Long task with an end | `ProgressBar` (+ "N / M") and a **Stop** action | while running |
| Nothing to show | `Kirigami.PlaceholderMessage` + `helpfulAction` | while empty |
| Destructive or work-losing action | `Kirigami.PromptDialog` with icon-labelled actions | modal |
| Long work finished/failed while the window is in the background | KNotification | system |
| Persistent background state | tray tooltip (`KStatusNotifierItem`) | always |

## Plumbing: controllers speak, the window shows

```python
class AppController(QObject):
    message = Signal(str)          # host.notify(text)
    problem = Signal(str)          # host.notify_error(text): also logged
```
```qml
Connections {
    target: root.app
    function onMessage(text) { root.showPassiveNotification(text) }
    function onProblem(text) { root.showPassiveNotification(text, "long", i18n("Show Log"), () => root.showPage("log")) }
}
```

Page controllers depend on the `Host` protocol, never on QML. fzonetrack carries a tone
(`notify = Signal(str, str)`: info/success/warning/error) and maps error → `"long"`.

## Inline messages

```qml
header: Kirigami.InlineMessage {
    position: Kirigami.InlineMessage.Position.Header
    type: messageTypes[controller.state] ?? Kirigami.MessageType.Information
    visible: text !== ""
    text: controller.statusText
    showCloseButton: controller.state !== "running"
    actions: Kirigami.Action { text: i18n("Retry"); icon.name: "view-refresh"; onTriggered: controller.reload() }
}
readonly property var messageTypes: ({ running: Kirigami.MessageType.Information,
    done: Kirigami.MessageType.Positive, failed: Kirigami.MessageType.Error,
    cancelled: Kirigami.MessageType.Warning })
```

Typical uses: "Saved. Takes effect after a restart" (Warning), "Paused" with Resume
(Information), "Stream disconnected" (Warning), "Update available" (Positive), an error with
Retry.

## Progress and cancel

```qml
Kirigami.InlineMessage {
    visible: browser.progress >= 0
    text: i18n("Preparing thumbnails… %1%", Math.round(browser.progress * 100))
    actions: Kirigami.Action { text: i18n("Stop"); icon.name: "process-stop"; onTriggered: browser.cancelWarm() }
}
QQC2.ProgressBar { visible: browser.progress >= 0; value: Math.max(0, browser.progress)
                   indeterminate: total <= 0 }   // unknown total → indeterminate
```

- Expose progress as one float (`-1` = no task) or `current/total` ints; push updates from
  the worker with `worker.post(...)` ([09](09-async-commands-files.md)).
- The Stop button shows "Stopping…" and disables itself until the job ends (fzonetrack).
- A blocking server call + out-of-band progress (SSE) is fine: the call's callback gives the
  summary, progress frames update the bar (fzonetrack auto-map).
- A status footer (`QQC2.ToolBar { position: Footer }`) for app-wide activity, visible only
  while there is something to say; dock it under the page stack, not as the window
  `footer` (which would run under a docked drawer — scraper).

## Empty, loading and error states

```qml
Kirigami.PlaceholderMessage {
    anchors.centerIn: parent
    width: parent.width - Kirigami.Units.gridUnit * 4
    visible: !hasRows && !busy
    icon.name: controller.empty.icon          // the controller decides which empty state
    text: controller.empty.title              // "This folder is empty" vs "Cannot read this folder"
    explanation: controller.empty.hint
    helpfulAction: Kirigami.Action { text: i18n("Open Folder…"); icon.name: "document-open-folder"; onTriggered: dialog.open() }
}
```

Distinguish *filtered-empty* ("No game matches the filter" + Clear filters) from *no data*
("Your library is empty" + Choose folder) from *error*. fzonetrack's startup is a
full-window `PlaceholderMessage` driven by a server state machine
(checking/starting/running/unreachable/failed) with Retry.

## Confirmation

Confirm only what loses work or deletes data; name the action on the button ("Delete 3
Files", "Quit"), never "OK". Quit confirmation via `onClosing` + `quitBlocker()` only while
work is running ([05](05-qml-kirigami-ui.md)). For destructive file operations prefer
**undo** (move to trash: `KIO::trash` in C++, `gio trash`/`QFile.moveToTrash` in Python)
over a dialog.

## Desktop notifications (KNotifications)

Policy (fzonetrack `core/notices.py`): notify only for the *end* of long work, only when
the window is not active; failures always notify. Everything else stays in-window.

```python
note = KNotification("thumbnailsReady", parent=self)   # id from <app>.notifyrc
note.setTitle(title); note.setText(text)
note.setIconName(APP_ID)
note.setWindow(window)                                  # click → raise our window
if failed: note.setUrgency(KNotification.Urgency.HighUrgency)
note.addDefaultAction("Open").activated.connect(raise_window)
self._live.add(note)                                    # keep the wrapper alive…
note.closed.connect(lambda: self._live.discard(note))   # …until closed, or the action is dead
note.sendEvent()
```

The `.notifyrc` lists the events; users tune them in System Settings → Notifications →
Applications ([12](12-desktop-integration.md)). Fallback without the binding: the tray's
`showMessage`, then nothing.

## Logs as feedback

A Log page fed by a `logging.Handler` that emits a Qt signal (thread-safe: the signal
crosses threads queued) into a capped `QAbstractListModel` (`deque(maxlen=5000)`,
`beginInsertRows`/`beginRemoveRows`). Level combo + `Kirigami.SearchField { delaySearch:
true }`; tone colours from `Kirigami.Theme`; `Kirigami.SelectableLabel` with
`fixedWidthFont`; follow the tail only while the user is at the end:

```qml
property bool following: true
onMovementEnded: following = atYEnd
onCountChanged: if (following) Qt.callLater(positionViewAtEnd)
```

Count warnings into a "problems" badge on the log button; clear it when the page is shown.
