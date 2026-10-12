import QtQuick
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami

// Always laid out, only its opacity changes: the content below never jumps.
QQC2.ProgressBar {
    property bool busy: false
    indeterminate: busy
    opacity: busy ? 1 : 0
    Behavior on opacity { OpacityAnimator { duration: Kirigami.Units.shortDuration } }
    Accessible.name: busy ? i18n("Loading") : ""
}
