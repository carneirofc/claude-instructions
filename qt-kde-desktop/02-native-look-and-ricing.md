# 02 — Native look & ricing

"Ricing" = the user customised their desktop (colour scheme, accent colour, widget style
such as Kvantum/Lightly/Klassy, icon theme, fonts, animation speed, scale). A native app
inherits all of it **for free**, as long as it never hard-codes any of it.

## The style chain

```
QApplication ─► platform theme plugin ─► QStyle (Breeze / Kvantum / Fusion …) ─► palette, fonts, icons
   │              plasma-integration on Plasma; qt6ct / xdgdesktopportal elsewhere
   └─► QQuickStyle "org.kde.desktop" (qqc2-desktop-style) draws Qt Quick Controls through that QStyle
        └─► Kirigami.Theme reads the KDE colour scheme (kdeglobals) → colours, fonts, colour sets
```

Requirements, each one load-bearing:

| Piece | Why | Python | C++ |
| --- | --- | --- | --- |
| `QApplication` (not `QGuiApplication`) | `org.kde.desktop` paints through `QStyle` (a Widgets class) | `QApplication([...])` | `QApplication app(argc, argv)` |
| Controls style | native controls in QML | `if not os.environ.get("QT_QUICK_CONTROLS_STYLE"): QQuickStyle.setStyle("org.kde.desktop")` | same with `qEnvironmentVariableIsEmpty` |
| Icon theme fallback | missing icons outside Plasma | `QIcon.setFallbackThemeName("breeze")` | `KIconTheme::initTheme()` before `QApplication` (KF ≥ 6.3) |
| Widget style fallback | Fusion looks foreign | (platform theme decides) | replace only Fusion: `if (app.style()->name() == "fusion"_L1) QApplication::setStyle(u"breeze"_s)` |
| Packages | runtime | `qqc2-desktop-style breeze-icons`, optdepend `plasma-integration` | same |

**Respect overrides.** Only *default* a style; never override `QT_QUICK_CONTROLS_STYLE`,
`QT_STYLE_OVERRIDE` or a style the platform theme picked. `QIcon.setFallbackThemeName`
changes the fallback only — `setThemeName("breeze")` would clobber the user's icon theme.
KDE's tutorial sets `QApplication::setStyle("breeze")` unconditionally; the template only
replaces Qt's Fusion fallback so a Kvantum user keeps Kvantum.

Outside Plasma (GNOME, Hyprland, Sway…), the user picks the bridge: `plasma-integration`
(set `QT_QPA_PLATFORMTHEME=kde`), `qt6ct`, or `xdgdesktopportal`. Document this in the
README; list `plasma-integration` as an optdepend.

## In QML: tokens only

**Never** a hex colour, a pixel size, a font family/size or a millisecond literal
(scraper `AGENTS.md`, enforced by review). Use:

| Need | Use |
| --- | --- |
| Spacing / sizes | `Kirigami.Units.smallSpacing`, `largeSpacing`, `gridUnit * N`, `iconSizes.small/smallMedium/medium/large/huge`, `cornerRadius` |
| Durations | `Kirigami.Units.shortDuration`, `longDuration`, `veryLongDuration`, `toolTipDelay` — they scale with Plasma's animation speed slider and become 0 when animations are off |
| Text & surfaces | `Kirigami.Theme.textColor`, `backgroundColor`, `alternateBackgroundColor`, `disabledTextColor`, `highlightColor`, `highlightedTextColor`, `linkColor`, `focusColor`, `hoverColor` |
| Semantics | `positiveTextColor` (success), `neutralTextColor` (warning), `negativeTextColor` (error), and the `*BackgroundColor` variants |
| Fonts | `Kirigami.Theme.defaultFont`, `smallFont`, `fixedWidthFont` (logs, paths, output) |
| Derived colours | `Kirigami.ColorUtils.tintWithAlpha(background, tone, 0.15)`, `Qt.alpha(Kirigami.Theme.textColor, 0.12)`, `Kirigami.ColorUtils.linearInterpolation(a, b, t)` |
| Headings | `Kirigami.Heading { level: 2 }` |

**Colour sets** scope a region to a role of the scheme; always pair with `inherit: false`:

```qml
Kirigami.Page {
    Kirigami.Theme.colorSet: Kirigami.Theme.View       // content lists/grids: Breeze's lighter "view"
    Kirigami.Theme.inherit: false
}
Rectangle {                                            // a header strip on the window surface
    Kirigami.Theme.colorSet: Kirigami.Theme.Window
    Kirigami.Theme.inherit: false
    color: Kirigami.Theme.backgroundColor
}
// Media viewers / galleries: Complementary (dark in Breeze, inverted in Breeze Dark)
// instead of a hard-coded near-black — scraper GalleryViewer does this.
```

Sets: `View`, `Window`, `Button`, `Selection`, `Tooltip`, `Complementary`, `Header`.

A semantic pill that follows any scheme (template `ToneBadge.qml`, from scraper):

```qml
QQC2.Label {
    readonly property color toneColor: tone === "bad" ? Kirigami.Theme.negativeTextColor
        : tone === "warn" ? Kirigami.Theme.neutralTextColor
        : tone === "good" ? Kirigami.Theme.positiveTextColor
        : tone === "accent" ? Kirigami.Theme.highlightColor : Kirigami.Theme.disabledTextColor
    color: toneColor
    font: Kirigami.Theme.smallFont
    background: Rectangle {
        radius: Kirigami.Units.cornerRadius
        color: Kirigami.ColorUtils.tintWithAlpha(Kirigami.Theme.backgroundColor, parent.toneColor, 0.15)
        border.color: Kirigami.ColorUtils.tintWithAlpha(Kirigami.Theme.backgroundColor, parent.toneColor, 0.4)
    }
}
```

## Window chrome

- **No client-side decorations**, no custom title bar: KWin (or the compositor) draws the
  user's window decoration (scraper rule).
- `pageStack.globalToolBar.style: Kirigami.ApplicationHeaderStyle.ToolBar` — the desktop
  pattern (a toolbar per column), not the mobile titles.
- **Remember size, never position**: on Wayland the compositor owns placement, and should
  everywhere (scraper has a test for it).
- Use `Kirigami.ApplicationWindow` sizes in `gridUnit` multiples (`minimumWidth: gridUnit * 22`).

## Controls

- Use QQC2 controls and Kirigami/kirigami-addons components; `org.kde.desktop` draws them
  with the user's style. A custom `background:` on a `Button` breaks that — style through
  `flat`, `highlighted`, `display`, `icon.name` instead.
- Delegates: `QQC2.ItemDelegate` with `highlighted:` — the style paints hover, selection
  and focus. `Kirigami.delegates.IconTitleSubtitle` for icon/title/subtitle content.
- Settings: kirigami-addons `FormCard` (System Settings' look). Native dialogs:
  `QtQuick.Dialogs.FolderDialog/FileDialog` → Dolphin's dialog via plasma-integration or
  the portal.

## Verify the ricing

```sh
plasma-apply-colorscheme BreezeDark   # then BreezeLight, BreezeClassic, a high-contrast one
QT_QUICK_CONTROLS_STYLE=Fusion myapp  # the override must win
QT_STYLE_OVERRIDE=kvantum myapp       # if kvantum is installed
QT_SCALE_FACTOR=1.5 myapp             # gridUnit scales; nothing clips
kwriteconfig6 --file kdeglobals --group KDE --key AnimationDurationFactor 0  # animations off
QT_QPA_PLATFORMTHEME=qt6ct myapp      # outside-Plasma path
```

Plus: change the accent colour, the icon theme (Papirus), the default font size — the app
must follow without restart where Kirigami does (colours do; some fonts need a restart).
