"""Internationalisation: KI18n's QML functions, backed by gettext.

KDE translates with gettext catalogs (.po/.mo). A C++ app gets ``i18n()`` & co in QML from
``KLocalization::setupLocalizedContext``; KI18n has no Python binding (and ``import
org.kde.ki18n`` from Python yields a null singleton), so this context object provides the
same functions:

- the app's own strings: ``i18n("Open %1", name)`` in QML, ``tr("...")`` in Python, both
  looked up in the ``myapp`` domain (po/*.po, compiled to <localedir>/<lang>/LC_MESSAGES/);
- KDE components' strings: kirigami-addons calls ``i18nd("kirigami-addons6", ...)``, found
  in the system's /usr/share/locale, so FormCard pages and the About page get translated
  too. (Kirigami itself loads its own Qt .qm translations; nothing to do.)

The language follows the desktop (QLocale.uiLanguages: System Settings → Region &
Language), and LANGUAGE=pt_BR overrides it for testing. Changing it needs a restart.
"""

from __future__ import annotations

import gettext
import os
import re
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from PySide6.QtCore import QCoreApplication as App
from PySide6.QtCore import QLibraryInfo, QLocale, QObject, QTranslator, Slot

DOMAIN = "myapp"
MAX_ARGS = 6
_PLACEHOLDER = re.compile(r"%(\d+)")
# Compiled catalogs of a source checkout (scripts/i18n.sh compile); packages use /usr/share/locale.
DEV_LOCALEDIR = Path(__file__).resolve().parent.parent / "locale"


def languages() -> list[str]:
    if forced := os.environ.get("LANGUAGE"):
        return [lang for lang in forced.split(":") if lang]
    # "pt-BR" -> "pt_BR", then the bare language as a fallback ("pt").
    found: list[str] = []
    for tag in QLocale().uiLanguages():
        name = tag.replace("-", "_")
        for candidate in (name, name.split("_")[0]):
            if candidate not in found:
                found.append(candidate)
    return found


class Catalogs:
    """gettext translations per domain, loaded on first use."""

    def __init__(self, langs: Sequence[str], app_localedir: Path | None) -> None:
        self._langs = list(langs)
        self._app_localedir = app_localedir
        self._loaded: dict[str, gettext.NullTranslations] = {}

    def get(self, domain: str) -> gettext.NullTranslations:
        if domain not in self._loaded:
            localedir = self._app_localedir if domain == DOMAIN else None  # None: /usr/share/locale
            self._loaded[domain] = gettext.translation(
                domain, localedir=localedir, languages=self._langs, fallback=True
            )
        return self._loaded[domain]


def substitute(text: str, args: Sequence[Any]) -> str:
    """KDE's %1..%n placeholders; a whole float prints as an int."""
    def value(n: int) -> str:
        arg = args[n - 1]
        return str(int(arg)) if isinstance(arg, float) and arg.is_integer() else str(arg)

    return _PLACEHOLDER.sub(
        lambda m: value(int(m[1])) if 0 < int(m[1]) <= len(args) else m[0], text)


def _count(args: Sequence[Any]) -> int:
    try:
        return int(args[0]) if args else 0
    except (TypeError, ValueError):
        return 0


def _overloads(leading: int) -> Callable[[Callable[..., str]], Callable[..., str]]:
    """QML calls i18n("x", a, b): PySide6 slots are not variadic, so stack one overload per
    arity on the same function (``leading`` strings, then 0..MAX_ARGS QVariants)."""
    def wrap(fn: Callable[..., str]) -> Callable[..., str]:
        for extra in range(MAX_ARGS, -1, -1):
            fn = Slot(*([str] * leading), *(["QVariant"] * extra), result=str)(fn)
        return fn
    return wrap


class LocalizedContext(QObject):
    def __init__(self, catalogs: Catalogs, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._c = catalogs

    def _t(self, domain: str, context: str | None, text: str, plural: str | None,
           args: Sequence[Any]) -> str:
        catalog = self._c.get(domain)
        if plural is None:
            out = catalog.pgettext(context, text) if context else catalog.gettext(text)
        elif context:
            out = catalog.npgettext(context, text, plural, _count(args))
        else:
            out = catalog.ngettext(text, plural, _count(args))
        return substitute(out, args)

    @_overloads(1)
    def i18n(self, text: str, *args: Any) -> str:
        return self._t(DOMAIN, None, text, None, args)

    @_overloads(2)
    def i18nc(self, context: str, text: str, *args: Any) -> str:
        return self._t(DOMAIN, context, text, None, args)

    @_overloads(2)
    def i18np(self, singular: str, plural: str, *args: Any) -> str:
        return self._t(DOMAIN, None, singular, plural, args)

    @_overloads(3)
    def i18ncp(self, context: str, singular: str, plural: str, *args: Any) -> str:
        return self._t(DOMAIN, context, singular, plural, args)

    @_overloads(2)
    def i18nd(self, domain: str, text: str, *args: Any) -> str:
        return self._t(domain, None, text, None, args)

    @_overloads(3)
    def i18ndc(self, domain: str, context: str, text: str, *args: Any) -> str:
        return self._t(domain, context, text, None, args)

    @_overloads(3)
    def i18ndp(self, domain: str, singular: str, plural: str, *args: Any) -> str:
        return self._t(domain, None, singular, plural, args)

    @_overloads(4)
    def i18ndcp(self, domain: str, context: str, singular: str, plural: str,
                *args: Any) -> str:
        return self._t(domain, context, singular, plural, args)


_context: LocalizedContext | None = None


def install(engine: Any) -> LocalizedContext:
    """Make i18n*() global to every QML file of ``engine``, translate Qt's own strings
    (standard buttons, dialogs), and enable tr() for Python code."""
    global _context
    app_dir = DEV_LOCALEDIR if DEV_LOCALEDIR.is_dir() else None
    _context = LocalizedContext(Catalogs(languages(), app_dir), engine)
    engine.rootContext().setContextObject(_context)
    qt = QTranslator(App.instance())
    if qt.load(QLocale(), "qt", "_", QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)):
        App.installTranslator(qt)
    return _context


def tr(text: str, *args: Any) -> str:
    """Python-side strings, same catalog as QML (xgettext keyword: tr)."""
    return _context.i18n(text, *args) if _context else substitute(text, args)


def trp(singular: str, plural: str, *args: Any) -> str:
    return _context.i18np(singular, plural, *args) if _context else substitute(
        singular if _count(args) == 1 else plural, args)
