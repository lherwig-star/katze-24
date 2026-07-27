"""Hilfsfunktionen zum Parsen von Preis- und Mengenangaben.

Reine Funktionen ohne Netzwerk - deshalb gut testbar. Wenn ihr beim Crawlen
merkt, dass ein Shop ein Format nutzt, das hier noch fehlt: Testfall in
tests/test_parse.py ergaenzen, dann Funktion erweitern.
"""

from __future__ import annotations

import re

_PRICE_RE = re.compile(r"(\d{1,3}(?:[.\s]\d{3})*|\d+)([,.]\d{1,2})?")

# "12 x 85 g", "2x400ml", "800 g", "1,5 kg", "6 Stk."
_UNIT_RE = re.compile(
    r"(?:(?P<count>\d+)\s*[x×]\s*)?"
    r"(?P<amount>\d+(?:[.,]\d+)?)\s*"
    r"(?P<unit>kg|g|l|ml|stk|stueck|stück)\b",
    re.IGNORECASE,
)

# Zielgroessen: Gewicht -> kg, Volumen -> l, Rest -> stk
_TO_BASE = {
    "g": (0.001, "kg"),
    "kg": (1.0, "kg"),
    "ml": (0.001, "l"),
    "l": (1.0, "l"),
    "stk": (1.0, "stk"),
    "stueck": (1.0, "stk"),
    "stück": (1.0, "stk"),
}


def parse_price(text: str) -> int | None:
    """'1.234,56 EUR' -> 123456 (Cent). Gibt None zurueck, wenn nichts drin ist.

    Geht von deutscher Schreibweise aus (Komma = Dezimaltrennzeichen,
    Punkt/Leerzeichen = Tausendertrennzeichen) - reicht fuer deutsche Shops.
    Achtung bei internationalen Quellen: '1,234.56' waere dort 1234,56,
    hier wird es (bewusst) als 1,23 gelesen.
    """
    if not text:
        return None
    cleaned = text.replace(" ", " ").strip()
    m = _PRICE_RE.search(cleaned)
    if not m:
        return None

    whole, frac = m.group(1), m.group(2)
    whole = re.sub(r"[.\s]", "", whole)
    cents = int(whole) * 100
    if frac:
        digits = frac[1:].ljust(2, "0")[:2]
        cents += int(digits)
    return cents


def parse_unit(text: str) -> tuple[float, str] | None:
    """'12 x 85 g' -> (1.02, 'kg'). None wenn keine Menge erkennbar.

    Wird fuer den Grundpreis gebraucht - der ist beim Vergleich zwischen
    Shops oft aussagekraeftiger als der Endpreis.
    """
    if not text:
        return None
    m = _UNIT_RE.search(text)
    if not m:
        return None

    amount = float(m.group("amount").replace(",", "."))
    count = int(m.group("count")) if m.group("count") else 1
    factor, base_unit = _TO_BASE[m.group("unit").lower()]
    return round(amount * count * factor, 6), base_unit


def clean_title(text: str) -> str:
    """Mehrfache Leerzeichen und Zeilenumbrueche rauswerfen."""
    return re.sub(r"\s+", " ", text or "").strip()
