# A KDE-native Kirigami app in C++: Qt 6 + KDE Frameworks 6, built with ECM.
# NOTE: the sources pass `g++ -fsyntax-only` against KF 6.30 / Qt 6.11 headers, but the
# project was never configured/linked (no cmake/extra-cmake-modules where it was written).
# Build it once before relying on it:
#   cmake -B build -G Ninja && cmake --build build && ./build/bin/myapp
cmake_minimum_required(VERSION 3.25)
project(myapp VERSION 0.1.0 LANGUAGES CXX)

set(QT_MIN_VERSION 6.8.0)
set(KF_MIN_VERSION 6.8.0)  # KLocalization::setupLocalizedContext, KIconTheme::initTheme

find_package(ECM ${KF_MIN_VERSION} REQUIRED NO_MODULE)
set(CMAKE_MODULE_PATH ${ECM_MODULE_PATH})

include(KDEInstallDirs)        # KDE_INSTALL_APPDIR, ..._METAINFODIR, ..._KNOTIFYRCDIR, ...
include(KDECMakeSettings)
include(KDECompilerSettings NO_POLICY_SCOPE)
include(ECMFindQmlModule)
include(ECMInstallIcons)
include(FeatureSummary)

find_package(Qt6 ${QT_MIN_VERSION} REQUIRED COMPONENTS
    Core Gui Qml Quick QuickControls2 Widgets Concurrent DBus)
find_package(KF6 ${KF_MIN_VERSION} REQUIRED COMPONENTS
    Kirigami CoreAddons I18n Config IconThemes Notifications DBusAddons KIO)

# Runtime QML modules: fail at configure time, not at first launch.
ecm_find_qmlmodule(org.kde.kirigami REQUIRED)
ecm_find_qmlmodule(org.kde.kirigamiaddons.formcard REQUIRED)
ecm_find_qmlmodule(org.kde.desktop REQUIRED)   # qqc2-desktop-style

qt_standard_project_setup(REQUIRES 6.8)
qt_policy(SET QTP0004 NEW)  # qmldir per subdirectory of the QML module

# i18n() domain for C++ and the QML context (setupLocalizedContext reads it).
add_compile_definitions(TRANSLATION_DOMAIN="myapp")

add_subdirectory(src)

ki18n_install(po)   # po/<lang>/myapp.po -> /usr/share/locale/<lang>/LC_MESSAGES/myapp.mo

install(FILES data/io.github.example.myapp.desktop DESTINATION ${KDE_INSTALL_APPDIR})
install(FILES data/io.github.example.myapp.metainfo.xml DESTINATION ${KDE_INSTALL_METAINFODIR})
install(FILES data/myapp.notifyrc DESTINATION ${KDE_INSTALL_KNOTIFYRCDIR})
install(FILES data/io.github.example.myapp.svg
        DESTINATION ${KDE_INSTALL_FULL_ICONDIR}/hicolor/scalable/apps)

feature_summary(WHAT ALL INCLUDE_QUIET_PACKAGES FATAL_ON_MISSING_REQUIRED_PACKAGES)
