# 04 — C++ / Qt 6 + KDE Frameworks 6

Template: [`templates/cpp-kirigami`](templates/cpp-kirigami) — the same app as the Python
template. **Status:** every `.cpp` passes `g++ -fsyntax-only` against Qt 6.11 / KF 6.30
headers and the CMake targets/macro options were checked against the installed CMake
files, but it was never configured or linked (no cmake/ECM where it was written). Build it
once before trusting it.

## CMake (ECM)

```cmake
find_package(ECM 6.8.0 REQUIRED NO_MODULE)
set(CMAKE_MODULE_PATH ${ECM_MODULE_PATH})
include(KDEInstallDirs)            # KDE_INSTALL_APPDIR, _METAINFODIR, _KNOTIFYRCDIR, _FULL_ICONDIR
include(KDECMakeSettings)
include(KDECompilerSettings NO_POLICY_SCOPE)
include(ECMFindQmlModule)

find_package(Qt6 6.8 REQUIRED COMPONENTS Core Gui Qml Quick QuickControls2 Widgets Concurrent DBus)
find_package(KF6 6.8 REQUIRED COMPONENTS Kirigami CoreAddons I18n Config IconThemes Notifications DBusAddons KIO)
ecm_find_qmlmodule(org.kde.kirigami REQUIRED)            # runtime QML deps fail at configure time
ecm_find_qmlmodule(org.kde.kirigamiaddons.formcard REQUIRED)
qt_standard_project_setup(REQUIRES 6.8)
add_compile_definitions(TRANSLATION_DOMAIN="myapp")

qt_add_executable(myapp main.cpp)
qt_add_qml_module(myapp URI io.github.example.myapp
    QML_FILES qml/Main.qml qml/BrowserPage.qml qml/SettingsPage.qml
    SOURCES backend.h backend.cpp thumbnailprovider.h thumbnailprovider.cpp commandrunner.h commandrunner.cpp)
kconfig_target_kcfg_file(myapp FILE myappconfig.kcfg CLASS_NAME Config
    MUTATORS NOTIFIERS DEFAULT_VALUE_GETTERS GENERATE_PROPERTIES GENERATE_MOC SINGLETON QML_REGISTRATION)
target_link_libraries(myapp PRIVATE Qt6::Quick Qt6::QuickControls2 Qt6::Widgets Qt6::Concurrent
    KF6::Kirigami KF6::CoreAddons KF6::I18n KF6::I18nQml KF6::ConfigCore KF6::ConfigGui
    KF6::IconThemes KF6::Notifications KF6::DBusAddons KF6::KIOGui)

ki18n_install(po)                                       # po/<lang>/myapp.po
install(TARGETS myapp ${KDE_INSTALL_TARGETS_DEFAULT_ARGS})
install(FILES data/<id>.desktop DESTINATION ${KDE_INSTALL_APPDIR})
install(FILES data/<id>.metainfo.xml DESTINATION ${KDE_INSTALL_METAINFODIR})
install(FILES data/myapp.notifyrc DESTINATION ${KDE_INSTALL_KNOTIFYRCDIR})   # /usr/share/knotifications6
install(FILES data/<id>.svg DESTINATION ${KDE_INSTALL_FULL_ICONDIR}/hicolor/scalable/apps)
```

KDE's own tutorial uses `ecm_add_qml_module` + `ecm_target_qml_sources`; `qt_add_qml_module`
is the plain-Qt equivalent and both work. `kconfig_target_kcfg_file` names the generated
header after the `.kcfg` (`myappconfig.h`).

## main.cpp

```cpp
KIconTheme::initTheme();                       // Breeze icons + KDE colour schemes outside Plasma
QApplication app(argc, argv);
if (qEnvironmentVariableIsEmpty("QT_STYLE_OVERRIDE") && app.style()->name() == "fusion"_L1)
    QApplication::setStyle(u"breeze"_s);       // replace only Qt's Fusion fallback (ricing)
if (qEnvironmentVariableIsEmpty("QT_QUICK_CONTROLS_STYLE"))
    QQuickStyle::setStyle(u"org.kde.desktop"_s);
KLocalizedString::setApplicationDomain("myapp");

KAboutData about(u"myapp"_s, i18n("My App"), QStringLiteral(PROJECT_VERSION_STRING), ...);
about.setDesktopFileName(u"io.github.example.myapp"_s);
KAboutData::setApplicationData(about);         // FormCard.AboutPage reads it — no aboutData needed

KDBusService service(KDBusService::Unique);    // single instance
QQmlApplicationEngine engine;
KLocalization::setupLocalizedContext(&engine); // <KLocalizedQmlContext>, KF6::I18nQml, KF ≥ 6.8
engine.addImageProvider(u"thumbs"_s, new ThumbnailProvider);
engine.loadFromModule("io.github.example.myapp", "Main");
QObject::connect(&service, &KDBusService::activateRequested, window, [window] {
    window->show(); window->raise(); window->requestActivate(); });
```

`KLocalizedContext` is **deprecated since KF 6.8**; `setupLocalizedContext` (declared in
`<KLocalizedQmlContext>`, not `<KLocalization>`) replaces it, re-evaluates bindings when
the language changes, and also exposes `KI18n.i18n()` for qmllint-friendly calls (KF 6.21+).

## Types for QML

```cpp
class Backend : public QObject {
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON                                   // QML: import io.github.example.myapp; Backend.open(...)
    Q_PROPERTY(QString title READ title NOTIFY folderChanged FINAL)
    Q_PROPERTY(FolderModel *folder READ folder CONSTANT FINAL)
public:
    Q_INVOKABLE void open(const QString &path);
Q_SIGNALS:
    void folderChanged();
    void message(const QString &text);
};

class FolderModel : public QAbstractListModel {
    Q_OBJECT
    QML_ELEMENT
    QML_UNCREATABLE("Provided by Backend.folder")
    ...
    QHash<int, QByteArray> roleNames() const override;   // names = delegates' required properties
};
```

`FINAL` on properties lets qmlcachegen/qmllint resolve them statically. The KConfigXT
`Config` singleton (`QML_REGISTRATION`) is bindable from QML (`Config.thumbnailSize`) and
written with `Config.thumbnailSize = v; Config.save()`.

## Async in C++

| Work | Tool |
| --- | --- |
| CPU/disk off the GUI thread, result back | `QtConcurrent::run(fn, args...)` + `QFutureWatcher` (`finished` fires on the GUI thread). `run()` futures cannot be cancelled — `setFuture()` on the watcher just stops watching the old one |
| Many small jobs (thumbnails) | a private `QThreadPool` + `QQuickAsyncImageProvider` responses |
| Network | `QNetworkAccessManager` (async on the GUI thread) |
| Processes | `QProcess` (async signals) — template `CommandRunner` |
| File operations with progress/undo | `KIO::copy/move/del` jobs + `KJobTrackerInterface` (progress shows in Plasma's notification area) |
| Coroutines | QCoro (`extra/qcoro`) if you want `co_await` on replies/processes |

## KNotification

```cpp
auto *n = new KNotification(u"thumbnailsReady"_s);   // id = [Event/thumbnailsReady] in myapp.notifyrc
n->setTitle(i18n("Thumbnails ready"));
n->setText(text);
n->setWindow(window);                                   // clicking raises this window
auto *open = n->addDefaultAction(i18n("Open"));
QObject::connect(open, &KNotificationAction::activated, window, &QWindow::requestActivate);
n->sendEvent();                                         // auto-deletes when closed
```

## Python ↔ C++ equivalence

| Concern | Python template | C++ template |
| --- | --- | --- |
| Expose backend | `setInitialProperties({"app": ctl})` | `QML_ELEMENT QML_SINGLETON` |
| Property | `qt_property(getter, int, notify=sig)` | `Q_PROPERTY(int x READ x NOTIFY xChanged FINAL)` |
| Method | `@Slot(int)` | `Q_INVOKABLE` |
| Settings | `QSettings(~/.config/myapprc)` + validation | KConfigXT `Config` (same file and keys) |
| i18n | gettext context object | KI18n `setupLocalizedContext` |
| Single instance | QtDBus `registerService` | `KDBusService::Unique` |
| Reveal file | FileManager1 over QtDBus | `KIO::highlightInFileManager` |
| Thumbnails | Pillow → WebP, sync `QQuickImageProvider` on loader threads | `QImageReader::setScaledSize` → `QImageWriter("webp")`, async provider + pool |
| Background work | asyncio worker + `Relay` | `QtConcurrent` + `QFutureWatcher` |
