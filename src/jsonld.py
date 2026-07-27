"""Gemeinsame Hilfsfunktionen zum Lesen von schema.org JSON-LD.

Viele Shops liefern ihre Produktdaten als JSON-LD im HTML (fuer Google Rich
Snippets gedacht). Das ist deutlich stabiler als CSS-Selektoren, weil Shops
es kaum aendern, ohne ihr SEO zu riskieren. Siehe CLAUDE.md: vor jedem neuen
Crawler zuerst hierauf pruefen, erst wenn nichts da ist auf CSS ausweichen.

Diese Funktionen sind bewusst generisch (kein Shop-Wissen drin), damit sie
fuer jeden neuen Shop wiederverwendbar sind - siehe zooplus.py und
fressnapf.py fuer zwei unterschiedliche Verschachtelungen, die beide
funktionieren.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterator
from typing import Any

log = logging.getLogger(__name__)

_LD_RE = re.compile(
    r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.S | re.I,
)


def iter_ld_blocks(html: str) -> Iterator[Any]:
    """Jeden JSON-LD-Block im HTML parsen. Kaputte Bloecke werden uebersprungen."""
    for raw in _LD_RE.findall(html):
        try:
            yield json.loads(raw)
        except json.JSONDecodeError:
            log.debug("JSON-LD nicht parsebar (%d Zeichen)", len(raw))


def find_by_type(html: str, type_name: str) -> Iterator[dict[str, Any]]:
    """Rekursiv alle Objekte eines schema.org-Typs im JSON-LD finden.

    Funktioniert unabhaengig davon, wie tief ein Shop seine Daten
    verschachtelt (z.B. mainEntity -> ItemList -> itemListElement -> item).
    """
    for block in iter_ld_blocks(html):
        yield from _walk(block, type_name)


def _walk(node: Any, type_name: str) -> Iterator[dict[str, Any]]:
    if isinstance(node, dict):
        if node.get("@type") == type_name:
            yield node
        for value in node.values():
            yield from _walk(value, type_name)
    elif isinstance(node, list):
        for item in node:
            yield from _walk(item, type_name)
