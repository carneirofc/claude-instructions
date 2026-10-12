"""gettext-backed i18n(): the app's catalog and KDE components' catalogs."""

from __future__ import annotations

from pathlib import Path

import pytest

from myapp.qt.i18n import Catalogs, LocalizedContext, substitute

KDE_CATALOG = Path("/usr/share/locale/pt_BR/LC_MESSAGES/kirigami-addons6.mo")


def test_placeholders_follow_kde_rules() -> None:
    assert substitute("%1 of %2", (3.0, 10)) == "3 of 10"
    assert substitute("%1 and %3", ("a",)) == "a and %3"


def test_untranslated_text_passes_through_with_plurals() -> None:
    ctx = LocalizedContext(Catalogs(["xx"], None))
    assert ctx.i18n("Open %1", "a.png") == "Open a.png"
    assert ctx.i18np("%1 file", "%1 files", 1) == "1 file"
    assert ctx.i18np("%1 file", "%1 files", 3) == "3 files"


@pytest.mark.skipif(not KDE_CATALOG.exists(), reason="kirigami-addons pt_BR catalog not installed")
def test_kde_components_are_translated_from_the_system_catalogs() -> None:
    ctx = LocalizedContext(Catalogs(["pt_BR"], None))
    assert ctx.i18ndc("kirigami-addons6", "@action:button", "Close") != "Close"


def test_the_app_catalog_is_used_when_compiled(tmp_path: Path) -> None:
    import subprocess

    po = Path(__file__).resolve().parents[1] / "po" / "pt_BR.po"
    out = tmp_path / "pt_BR" / "LC_MESSAGES" / "myapp.mo"
    out.parent.mkdir(parents=True)
    subprocess.run(["msgfmt", "--check", "-o", str(out), str(po)], check=True)
    ctx = LocalizedContext(Catalogs(["pt_BR"], tmp_path))
    assert ctx.i18n("Settings") == "Configurações"
    plural = ctx.i18np("Prepared %1 thumbnail", "Prepared %1 thumbnails", 2)
    assert plural == "2 miniaturas preparadas"
