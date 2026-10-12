# 06 — Animation

## Vocabulary (the whole set)

| Token | Use |
| --- | --- |
| `Kirigami.Units.shortDuration` | hover, press, small fades, busy line, chip state |
| `Kirigami.Units.longDuration` | page enter, view switch, image fade-in, list populate |
| `Kirigami.Units.veryLongDuration` | slow emphasis (cover zoom), rarely |
| `Easing.OutCubic` | default for everything entering or settling |
| `Easing.InOutQuad` | position changes between two resting states |

The durations follow Plasma's animation-speed slider and become 0 when animations are
disabled: **no millisecond literals** (debounce timers are not animations — they may use
numbers). Animate `opacity`, `scale` and `transform: Translate` — cheap, no relayout. Prefer
`OpacityAnimator`/`ScaleAnimator` (render thread) when the target is known up front.

## Recipes

**Page enter, safe against interruption** (fzonetrack, template):

```qml
ParallelAnimation {
    id: pageEnter
    property Item page
    NumberAnimation { target: pageEnter.page; property: "opacity"; from: 0; to: 1
                      duration: Kirigami.Units.longDuration; easing.type: Easing.OutCubic }
    NumberAnimation { target: pageEnter.page; property: "scale"; from: 0.98; to: 1
                      duration: Kirigami.Units.longDuration; easing.type: Easing.OutCubic }
    // A switch mid-animation must not leave a page half-transparent.
    onStopped: if (page) { page.opacity = 1; page.scale = 1; }
}
```

**Grid ⇄ list switch:** `Loader { onLoaded: { item.opacity = 0; fade.restart() } }` with an
`OpacityAnimator` — or opacity + `Translate { y: gridUnit * 2 → 0 }` (scraper).

**List population:**

```qml
populate: Transition { NumberAnimation { properties: "opacity"; from: 0; to: 1; duration: Kirigami.Units.longDuration } }
add:      Transition { NumberAnimation { properties: "opacity,scale"; from: 0.96; to: 1; duration: Kirigami.Units.longDuration; easing.type: Easing.OutCubic } }
displaced: Transition { NumberAnimation { properties: "x,y"; duration: Kirigami.Units.shortDuration; easing.type: Easing.OutCubic } }
```

A model *reset* (whole new list) only plays `populate`; per-row `dataChanged` keeps
delegates and their running animations.

**Hover lift / press** (fzonetrack grid cards):

```qml
scale: tap.pressed ? 0.98 : hover.hovered ? 1.03 : 1
Behavior on scale { NumberAnimation { duration: Kirigami.Units.longDuration; easing.type: Easing.OutCubic } }
Behavior on shadow.size { NumberAnimation { duration: Kirigami.Units.longDuration } }   // Kirigami.ShadowedRectangle
```

**Image fade-in** (all three apps):

```qml
Image {
    asynchronous: true
    opacity: status === Image.Ready ? 1 : 0
    Behavior on opacity { NumberAnimation { duration: Kirigami.Units.longDuration; easing.type: Easing.OutCubic } }
}
Kirigami.Icon { source: mimeIcon; visible: image.status !== Image.Ready }   // placeholder underneath
```

**Indicators that don't shift layout:** keep them laid out, animate opacity only.

```qml
QQC2.ProgressBar { indeterminate: busy; opacity: busy ? 1 : 0
                   Behavior on opacity { OpacityAnimator { duration: Kirigami.Units.shortDuration } } }
```

**Expand/collapse:** `Behavior on implicitHeight { NumberAnimation { duration: Kirigami.Units.shortDuration } }` (scraper `TagBar`).

**Direction-aware content slide** (fzonetrack detail page): on row change compute
`direction = Math.sign(newPos - oldPos)`, animate `contentShift.x` from
`direction * gridUnit * 3` to 0 plus opacity 0.2 → 1.

**Hero transition into a viewer** (scraper `GalleryViewer`): capture the thumbnail rect with
`mapToItem(QQC2.Overlay.overlay, 0, 0)`, animate a proxy `Image`'s x/y/width/height to full
window inside the Popup's `enter` transition (`SequentialAnimation` + `PropertyAction`
for visibility).

**Popup enter/exit:** `enter: Transition { NumberAnimation { property: "scale"; from: 0.94; to: 1 } }`.

**Auto-hiding chrome** in viewers: a 2.5 s timer, `opacity` + `visible: opacity > 0` with a
Behavior, and `HoverHandler { cursorShape: chromeVisible ? Qt.ArrowCursor : Qt.BlankCursor }`.

## Pitfalls

- Restarting an animation mid-flight: call `complete()` first or reset in `onStopped`.
- `Behavior` on a property also animates programmatic jumps (e.g. restoring state) —
  disable with `enabled:` during bulk updates.
- `reuseItems: true` + per-delegate animations: reset in `ListView.onReused`.
- Don't animate `width`/`height` of items in layouts (relayout per frame); animate
  `implicitHeight` of a clipped container or use transforms.
