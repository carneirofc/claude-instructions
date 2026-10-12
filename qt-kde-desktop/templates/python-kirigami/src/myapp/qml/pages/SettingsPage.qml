import QtQuick
import org.kde.kirigami as Kirigami
import org.kde.kirigamiaddons.formcard as FormCard

// KDE-style preferences: FormCard sections, applied live (no OK/Apply for simple prefs).
// Each control reads the controller and writes back through a setter slot that validates;
// a rejected value shows as the field's status message.
FormCard.FormCardPage {
    id: page

    readonly property QtObject app: applicationWindow().app
    readonly property QtObject settings: app.settings

    title: i18n("Settings")

    FormCard.FormHeader { title: i18n("Appearance") }
    FormCard.FormCard {
        FormCard.FormSpinBoxDelegate {
            label: i18n("Thumbnail size")
            from: 64; to: 512; stepSize: 16
            value: page.settings.thumbnailSize
            onValueModified: page.settings.setThumbnailSize(value)
        }
        FormCard.FormDelegateSeparator {}
        FormCard.FormSwitchDelegate {
            text: i18n("Show hidden files")
            checked: page.settings.showHidden
            onToggled: page.settings.setShowHidden(checked)
        }
    }

    FormCard.FormHeader { title: i18n("Storage") }
    FormCard.FormCard {
        FormCard.FormSpinBoxDelegate {
            label: i18n("Thumbnail cache limit (MB)")
            from: 16; to: 8192; stepSize: 64
            value: page.settings.cacheMegabytes
            onValueModified: page.settings.setCacheMegabytes(value)
        }
        FormCard.FormDelegateSeparator {}
        FormCard.FormButtonDelegate {
            text: i18n("Clear thumbnail cache")
            icon.name: "edit-clear-all"
            onClicked: page.app.clearCache()
        }
    }

    FormCard.FormHeader { title: i18n("Commands") }
    FormCard.FormCard {
        FormCard.FormTextFieldDelegate {
            label: i18n("Command run on a file (its path is appended)")
            text: page.settings.command
            status: Kirigami.MessageType.Error
            statusMessage: page.settings.problem
            onEditingFinished: page.settings.setCommand(text)
        }
    }
}
