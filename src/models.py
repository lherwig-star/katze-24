"""Gemeinsame Datenmodelle.

Das hier ist der Vertrag zwischen allen Modulen: Ein Crawler liefert `Offer`s,
die Deal-Engine macht daraus `Deal`s, der Notifier verschickt sie.

WICHTIG: Diese Datei aendern wir nur gemeinsam. Wenn jeder hier eigene Felder
reinschreibt, kracht es beim Mergen.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class Offer:
    """Ein Produkt zu einem Zeitpunkt bei einem Shop.

    Preise sind IMMER Integer in Cent. Nie float - sonst hat man irgendwann
    19.989999999 im Vergleich und wundert sich.
    """

    shop: str  # Kurzname des Shops, identisch mit BaseCrawler.shop
    product_id: str  # Shop-interne ID oder URL-Slug, muss stabil sein
    title: str
    price_cents: int
    url: str

    brand: str | None = None
    list_price_cents: int | None = None  # Streichpreis, den der SHOP selbst
    # angibt (z.B. schema.org/ListPrice) - anders als eine UVP, die der Shop
    # nur behaupten koennte, ist das ein strukturiertes Feld des Shops selbst.
    is_marked_down: bool = False  # Shop markiert es als reduziert, aber ohne
    # exakten Streichpreis (z.B. Zugehoerigkeit zu einer Sale-Kategorie).
    category: str | None = None  # grobe Einordnung fuer den Bericht,
    # z.B. "Futter", "Streu", "Spielzeug" - vom jeweiligen Crawler vergeben.
    image_url: str | None = None
    unit_amount: float | None = None  # z.B. 1.02 (fuer 12 x 85 g)
    unit: str | None = None  # "kg" | "l" | "stk"
    available: bool = True
    seen_at: datetime = field(default_factory=_now)

    def __post_init__(self) -> None:
        if not self.shop or not self.product_id:
            raise ValueError("shop und product_id duerfen nicht leer sein")
        if self.price_cents <= 0:
            raise ValueError(f"unplausibler Preis: {self.price_cents} Cent")
        if not self.url.startswith("http"):
            raise ValueError(f"url muss absolut sein, war: {self.url!r}")

    @property
    def uid(self) -> str:
        """Eindeutige ID ueber alle Shops hinweg."""
        return f"{self.shop}:{self.product_id}"

    @property
    def price_per_unit_cents(self) -> float | None:
        """Grundpreis, z.B. Cent pro kg. None wenn Menge unbekannt."""
        if not self.unit_amount:
            return None
        return self.price_cents / self.unit_amount


@dataclass(frozen=True)
class Deal:
    """Ein Angebot, das die Deal-Engine fuer meldenswert haelt."""

    offer: Offer
    ref_price_cents: int  # Vergleichspreis, gegen den gerechnet wurde
    discount_pct: float
    reason: str  # menschenlesbar, z.B. "Tiefstpreis der letzten 90 Tage"
    score: float  # hoeher = besser, nur fuer Sortierung
    is_all_time_low: bool = False
