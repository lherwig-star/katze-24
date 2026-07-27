"""Entscheidet, was ein Deal ist.

Das ist der intellektuell interessanteste Teil des Projekts - viel mehr als
das Crawlen. Kernproblem:

  Der Streichpreis der Shops luegt fast immer. "Statt 39,99 EUR nur 19,99!"
  heisst meistens, dass das Produkt seit zwei Jahren 19,99 kostet.

Deshalb: Ein Deal ist ein Preis, der gegen die EIGENE gemessene Historie
niedrig ist. Nicht gegen die UVP.

Konsequenz: In den ersten Wochen findet ihr fast nichts, weil die Historie
fehlt. Das ist richtig so und kein Bug. Lasst den Crawler trotzdem taeglich
laufen - die Daten koennt ihr nicht nachtraeglich erzeugen.
"""

from __future__ import annotations

import logging
import statistics
from collections.abc import Iterable

from src.models import Deal, Offer
from src.storage import Store

log = logging.getLogger(__name__)

# Ab wie vielen Tagen Historie vertrauen wir unseren eigenen Daten?
MIN_HISTORY_POINTS = 7
HISTORY_DAYS = 90

# Schwellen
MIN_DISCOUNT_PCT = 15.0  # gegen eigene Historie
MIN_LIST_DISCOUNT_PCT = 35.0  # gegen Streichpreis - hoeher, weil unzuverlaessig


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
    """Ein einzelnes Angebot bewerten. None = kein Deal."""
    history = store.price_history(offer.uid, days=HISTORY_DAYS)

    if len(history) >= MIN_HISTORY_POINTS:
        return _evaluate_against_history(offer, history, min_discount)

    # Noch zu wenig eigene Daten -> notgedrungen der Streichpreis,
    # aber mit deutlich strengerer Schwelle und ehrlicher Begruendung.
    if offer.list_price_cents and offer.list_price_cents > offer.price_cents:
        discount = _pct(offer.price_cents, offer.list_price_cents)
        if discount >= MIN_LIST_DISCOUNT_PCT:
            return Deal(
                offer=offer,
                ref_price_cents=offer.list_price_cents,
                discount_pct=discount,
                reason=f"{discount:.0f}% unter Streichpreis (noch keine eigene Historie)",
                score=discount * 0.5,  # abgewertet, weil unsicher
            )
    return None


def _evaluate_against_history(
    offer: Offer, history: list[int], min_discount: float
) -> Deal | None:
    reference = int(statistics.median(history))
    if reference <= offer.price_cents:
        return None

    discount = _pct(offer.price_cents, reference)
    if discount < min_discount:
        return None

    all_time_low = offer.price_cents < min(history)
    score = discount + (15.0 if all_time_low else 0.0)

    if all_time_low:
        reason = f"Tiefstpreis seit {len(history)} Tagen ({discount:.0f}% unter dem Ueblichen)"
    else:
        reason = f"{discount:.0f}% unter dem ueblichen Preis ({_eur(reference)})"

    return Deal(
        offer=offer,
        ref_price_cents=reference,
        discount_pct=discount,
        reason=reason,
        score=score,
        is_all_time_low=all_time_low,
    )


def _pct(price: int, reference: int) -> float:
    return (1 - price / reference) * 100


def _eur(cents: int) -> str:
    return f"{cents / 100:.2f} EUR".replace(".", ",")
