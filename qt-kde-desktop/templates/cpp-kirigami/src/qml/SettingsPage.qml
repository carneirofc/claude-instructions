import QtQuick
import org.kde.kirigamiaddons.formcard as FormCard
import io.github.example.myapp

// Config is the KConfigXT singleton (QML_REGISTRATION): typed properties with notifiers;
// write through the setter, persist with save().
FormCard.FormCardPage {
    title: i18n("Settings")

    FormCard.FormHeader { title: i18n("Appearance") }
    FormCard.FormCard {
        FormCard.FormSpinBoxDelegate {
            label: i18n("Thumbnail size")
            from: 64; to: 512; stepSize: 16
            value: Config.thumbnailSize
            onValueModified: { Config.thumbnailSize = value; Config.save(); }
        }
        FormCard.FormSwitchDelegate {
            text: i18n("Show hidden files")
            checked: Config.showHidden
            onToggled: { Config.showHidden = checked; Config.save(); Backend.open(Backend.folderPath); }
        }
    }
    FormCard.FormHeader { title: i18n("Commands") }
    FormCard.FormCard {
        FormCard.FormTextFieldDelegate {
            label: i18n("Command run on a file (its path is appended)")
            text: Config.command
            onEditingFinished: { Config.command = text; Config.save(); }
        }
    }
}
