"""Auto-Discovery: importiert beim Laden jedes Modul in diesem Ordner.

Dadurch registrieren sich alle Crawler von selbst. Ihr muesst hier NICHTS
eintragen, wenn ihr einen neuen Crawler baut - einfach eine neue .py-Datei
in diesen Ordner legen.
"""

from __future__ import annotations

import importlib
import logging
import pkgutil
from pathlib import Path

from src.crawlers.base import REGISTRY, BaseCrawler, get_crawlers

log = logging.getLogger(__name__)

__all__ = ["REGISTRY", "BaseCrawler", "get_crawlers"]


def _discover() -> None:
    for module in pkgutil.iter_modules([str(Path(__file__).parent)]):
        if module.name.startswith("_") or module.name == "base":
            continue
        try:
            importlib.import_module(f"{__name__}.{module.name}")
        except Exception:
            # Ein kaputter Crawler soll nicht die anderen mitreissen.
            log.exception("Crawler-Modul %r konnte nicht geladen werden", module.name)


_discover()
