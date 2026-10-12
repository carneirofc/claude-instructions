# My App — Python + Kirigami template

A small but complete KDE-native app: a native-dialog image folder browser with a WebP
thumbnail cache, external command runs with streamed output, gettext translations, desktop
notifications, single instance, and Arch packaging. Every pattern is explained in
`../../` (the guide). Copy this directory to start a project, then follow the rename
checklist in `src/myapp/__init__.py`.

    sudo pacman -S --needed $(scripts/setup.sh --deps)
    uv lock && scripts/setup.sh        # .venv on the system Python + system PySide6
    scripts/dev.sh                     # run from source
    scripts/dev.sh pytest -q           # headless tests (QML warnings fail them)
    scripts/i18n.sh update             # refresh po/ after changing strings
    git init && git add -A && git commit -m "feat: initial import"
    scripts/package.sh -si             # build the pacman package from HEAD and install it
