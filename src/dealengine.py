"""Entscheidet, was ein Deal ist.

FRUEHERE VERSION dieser Datei hat einen Deal ausschliesslich gegen die
EIGENE gemessene Preishistorie erkannt (Streichpreise der Shops sind oft
Mondpreise - "statt 39,99 EUR nur 19,99!" heisst meistens, dass das Produkt
seit zwei Jahren 19,99 kostet).

Das ist inhaltlich weiterhin richtig, trifft aber nicht, was die Nutzer
im Kanal eigentlich wollen: Denen ist es egal, ob der Streichpreis fair
ist - die wollen einen sichtbaren Rabatt sehen und zugreifen. Ausserdem
braucht die Historie mehrere Wochen, bis sie ueberhaupt etwas findet.

DESHALB JETZT: Ausschlaggebend ist, ob der SHOP SELBST das Produkt als
reduziert markiert (siehe Offer.list_price_cents / Offer.is_marked_down,
kommt strukturiert aus dem jeweiligen Crawler - z.B. Zooplus' eigenes
schema.org/ListPrice-Feld oder Fressnapfs Sale-Kategorie). Die eigene
Preishistorie wird nicht mehr zur Bedingung, sondern nur noch als
Zusatz-Info in der Nachricht genutzt ("...und das ist sogar Tiefstpreis
der letzten 30 Tage").
"""

from __future__ import annotations

import logging
from collections.abc import Iterable

from src.models import Deal, Offer
from src.storage import Store

log = logging.getLogger(__name__)

HISTORY_DAYS = 90
MIN_HISTORY_POINTS = 7

# Nur um Rundungsrauschen rauszufiltern (z.B. 19,99 EUR "statt" 20,00 EUR) -
# nicht um den Rabatt in Frage zu stellen, das macht bewusst der Shop selbst.
MIN_DISCOUNT_PCT = 5.0


def find_deals(
    store: Store,
    offers: Iterable[Offer],
    min_discount: float = MIN_DISCOUNT_PCT,
) -> list[Deal]:
    """Alle Angebote bewerten und die interessanten zurueckgeben."""
    deals: list[Deal] = []
    for offer in offers:
        if not offer.available:
            continue
        deal = evaluate(store, offer, min_discount)
        if deal:
            deals.append(deal)
    deals.sort(key=lambda d: d.score, reverse=True)
    return deals


def evaluate(store: Store, offer: Offer, min_discount: float) -> Deal | None:
    """Ein einzelnes Angebot bewerten. None = kein Deal.

    Voraussetzung ist IMMER eine Markierung durch den Shop selbst - eine
    reine Preisschwankung in unserer eigenen Historie reicht nicht (mehr).
    """
    has_list_price = bool(offer.list_price_cents and offer.list_price_cents > offer.price_cents)
    if not has_list_price and not offer.is_marked_down:
        return None

    if has_list_price:
        discount = _pct(offer.price_cents, offer.list_price_cents)
        if discount < min_discount:
            return None
        ref_price = offer.list_price_cents
        reason = f"{discount:.0f}% reduziert (statt {_eur(offer.list_price_cents)})"
    else:
        # is_marked_down ohne exakten Streichpreis, z.B. Fressnapf-Sale-
        # Kategorie: wir wissen "reduziert", aber nicht um wieviel.
        discount = 0.0
        ref_price = offer.price_cents
        reason = "vom Shop als reduziert markiert"

    all_time_low, history_days = _check_history(store, offer)
    if all_time_low:
        reason += f" - zugleich Tiefstpreis der letzten {history_days} Tage"

    score = discount + (15.0 if all_time_low else 0.0)
    return Deal(
        offer=offer,
        ref_price_cents=ref_price,
        discount_pct=discount,
        reason=reason,
        score=score,
        is_all_time_low=all_time_low,
    )


def _check_history(store: Store, offer: Offer) -> tuple[bool, int]:
    """Nur noch Zusatz-Info, kein Gate mehr: ist der Rabatt sogar ein Tiefstpreis?"""
    history = store.price_history(offer.uid, days=HISTORY_DAYS)
    if len(history) < MIN_HISTORY_POINTS:
        return False, 0
    return offer.price_cents <= min(history), len(history)


def _pct(price: int, reference: int) -> float:
    return (1 - price / reference) * 100


def _eur(cents: int) -> str:
    return f"{cents / 100:.2f} EUR".replace(".", ",")
