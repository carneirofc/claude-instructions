qt_add_executable(myapp main.cpp)

# One QML module: the C++ types marked QML_ELEMENT/QML_SINGLETON and the .qml files,
# compiled into the binary (qrc) and loaded with engine.loadFromModule(URI, "Main").
qt_add_qml_module(myapp
    URI io.github.example.myapp
    QML_FILES
        qml/Main.qml
        qml/BrowserPage.qml
        qml/SettingsPage.qml
    SOURCES
        backend.h backend.cpp
        thumbnailprovider.h thumbnailprovider.cpp
        commandrunner.h commandrunner.cpp
)

# Settings as a typed, generated class (KConfigXT): ~/.config/myapprc
kconfig_target_kcfg_file(myapp FILE myappconfig.kcfg CLASS_NAME Config
    MUTATORS NOTIFIERS DEFAULT_VALUE_GETTERS GENERATE_PROPERTIES GENERATE_MOC SINGLETON
    QML_REGISTRATION)

target_compile_definitions(myapp PRIVATE PROJECT_VERSION_STRING="${PROJECT_VERSION}")

target_link_libraries(myapp PRIVATE
    Qt6::Quick Qt6::QuickControls2 Qt6::Widgets Qt6::Concurrent Qt6::DBus
    KF6::Kirigami KF6::CoreAddons KF6::I18n KF6::I18nQml KF6::ConfigCore KF6::ConfigGui
    KF6::IconThemes KF6::Notifications KF6::DBusAddons KF6::KIOGui)

install(TARGETS myapp ${KDE_INSTALL_TARGETS_DEFAULT_ARGS})
