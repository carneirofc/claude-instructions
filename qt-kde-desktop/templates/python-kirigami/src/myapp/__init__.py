"""My App: a KDE-native Kirigami desktop app (reference template).

Rename checklist: the package (``myapp``), APP_ID, APP_NAME, DISPLAY_NAME, the icon file
``data/icons/<APP_ID>.svg``, ``data/knotifications6/<APP_NAME>.notifyrc``, and the files
in packaging/arch/.
"""

from importlib.metadata import PackageNotFoundError, version

# One reverse-DNS id everywhere: the .desktop file name, the icon name, the AppStream id,
# the D-Bus service name and the Wayland app id (QGuiApplication.desktopFileName).
APP_ID = "io.github.example.myapp"
# The component name: QSettings directory and the notifyrc file name.
APP_NAME = "myapp"
DISPLAY_NAME = "My App"

try:
    __version__ = version("myapp")
except PackageNotFoundError:  # running from a source tree without an install
    __version__ = "0.0.0"
