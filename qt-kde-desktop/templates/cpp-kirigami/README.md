# My App — C++ + Kirigami template

The C++ counterpart of `../python-kirigami`: same app id, same settings file
(`~/.config/myapprc`), same desktop/AppStream/notification files, same patterns, in the KDE
Frameworks idiom (KAboutData, KDBusService, KLocalization, KConfigXT, KIO, QtConcurrent).

**Status: syntax-checked, never built.** Every `.cpp` passes `g++ -std=c++20 -fsyntax-only`
against the installed Qt 6.11 / KF 6.30 headers, and the CMake targets and `kconfig` macro
options were checked against the installed CMake files; but cmake/extra-cmake-modules were
not installed, so it was never configured, linked or run. Build it once before relying on it:

    sudo pacman -S --needed cmake ninja extra-cmake-modules qt6-tools kirigami kirigami-addons \
        qqc2-desktop-style ki18n kconfig kcoreaddons kiconthemes knotifications kdbusaddons kio
    cmake -B build -G Ninja -DCMAKE_INSTALL_PREFIX=$HOME/.local && cmake --build build
    ./build/bin/myapp

Translations use KDE's layout: `po/<lang>/myapp.po`, installed by `ki18n_install(po)`.
Copy `scripts/` from the Python template (lib.sh contract) and adapt `project.sh`.
