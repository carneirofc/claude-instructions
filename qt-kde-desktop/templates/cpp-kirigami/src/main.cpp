// Start the app the way KDE's own Kirigami apps do. Same order as the Python template's
// app.py: identity, style, icons, single instance, engine, load.

#include <QApplication>
#include <QIcon>
#include <QQmlApplicationEngine>
#include <QQuickStyle>
#include <QQuickWindow>
#include <QStyle>

#include <KAboutData>
#include <KDBusService>
#include <KIconTheme>
#include <KLocalizedQmlContext>  // KLocalization::setupLocalizedContext (KF6::I18nQml)
#include <KLocalizedString>

#include "thumbnailprovider.h"

using namespace Qt::Literals::StringLiterals;

int main(int argc, char *argv[])
{
    // Breeze icons and KDE colour schemes also outside Plasma (KF >= 6.3). Before the app.
    KIconTheme::initTheme();
    QApplication app(argc, argv);

    // Ricing-friendly: keep a style the user or the platform theme picked (Kvantum,
    // Lightly, ...); only replace Qt's built-in Fusion fallback with Breeze.
    if (qEnvironmentVariableIsEmpty("QT_STYLE_OVERRIDE") && app.style()->name() == "fusion"_L1) {
        QApplication::setStyle(u"breeze"_s);
    }
    if (qEnvironmentVariableIsEmpty("QT_QUICK_CONTROLS_STYLE")) {
        QQuickStyle::setStyle(u"org.kde.desktop"_s);
    }

    KLocalizedString::setApplicationDomain("myapp");  // before the first i18n() call

    KAboutData about(u"myapp"_s, i18n("My App"), QStringLiteral(PROJECT_VERSION_STRING),
                     i18n("Browse image folders with a native look"), KAboutLicense::MIT,
                     i18n("© 2026 Your Name"));
    about.addAuthor(i18n("Your Name"), i18n("Author"), u"you@example.org"_s);
    about.setHomepage(u"https://example.org/myapp"_s);
    about.setBugAddress("https://example.org/myapp/issues");
    about.setDesktopFileName(u"io.github.example.myapp"_s);  // Wayland app id
    KAboutData::setApplicationData(about);  // FormCard.AboutPage, notifications, D-Bus read it
    QApplication::setWindowIcon(QIcon::fromTheme(u"io.github.example.myapp"_s));

    // Single instance: a second launch activates the first and exits.
    KDBusService service(KDBusService::Unique);

    QQmlApplicationEngine engine;
    KLocalization::setupLocalizedContext(&engine);  // i18n() & KI18n.i18n() in QML (KF >= 6.8)
    engine.addImageProvider(u"thumbs"_s, new ThumbnailProvider);  // engine takes ownership
    engine.loadFromModule("io.github.example.myapp", "Main");
    if (engine.rootObjects().isEmpty()) {
        return 1;
    }

    auto *window = qobject_cast<QQuickWindow *>(engine.rootObjects().first());
    QObject::connect(&service, &KDBusService::activateRequested, window, [window] {
        window->show();
        window->raise();
        window->requestActivate();
    });

    return app.exec();
}
