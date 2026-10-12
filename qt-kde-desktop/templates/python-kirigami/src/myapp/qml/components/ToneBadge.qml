import QtQuick
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami

// A small status pill in the colour scheme's semantic colours: it follows Breeze, Breeze
// Dark, or any custom scheme, and its accent colour.
QQC2.Label {
    id: badge

    property string tone: "neutral"  // neutral | accent | good | warn | bad

    readonly property color toneColor: {
        switch (tone) {
        case "good": return Kirigami.Theme.positiveTextColor;
        case "warn": return Kirigami.Theme.neutralTextColor;
        case "bad": return Kirigami.Theme.negativeTextColor;
        case "accent": return Kirigami.Theme.highlightColor;
        default: return Kirigami.Theme.disabledTextColor;
        }
    }

    visible: text !== ""
    font: Kirigami.Theme.smallFont
    color: toneColor
    leftPadding: Kirigami.Units.smallSpacing
    rightPadding: Kirigami.Units.smallSpacing
    background: Rectangle {
        radius: Kirigami.Units.cornerRadius
        color: Kirigami.ColorUtils.tintWithAlpha(Kirigami.Theme.backgroundColor, badge.toneColor, 0.15)
        border.color: Kirigami.ColorUtils.tintWithAlpha(Kirigami.Theme.backgroundColor, badge.toneColor, 0.4)
    }
    Accessible.name: text
}
