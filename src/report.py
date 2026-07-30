"""Taeglicher Bericht: die besten Deals gruppiert nach Kategorie.

Gedacht fuer die manuelle Review, BEVOR etwas in den WhatsApp-Kanal geht -
ihr bekommt eine fertige Auswahl zum Durchlesen und Kopieren, sucht euch
aus, was rein soll, und postet das von Hand.

Die Rueckgabe ist eine Liste von "Haeppchen" (ein Kapitel pro Kategorie),
nicht ein einziger grosser Text - Telegram-Nachrichten sind auf 4096
Zeichen begrenzt, und pro Kategorie eine eigene Nachricht liest sich
ohnehin uebersichtlicher als eine Textwand.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date

from src.models import Deal
from src.notifier import format_deal

TELEGRAM_MSG_LIMIT = 4096
SONSTIGES = "Sonstiges"  # Kategorie unbekannt, z.B. Fressnapf-Sale-Fund


def build_report(deals: list[Deal], top_per_category: int = 5) -> list[str]:
    """Deals nach Kategorie gruppieren, pro Kategorie nur die besten N.

    Erstes Element der Liste ist eine kurze Kopfzeile mit der Gesamtzahl,
    danach ein Haeppchen pro Kategorie - sortiert nach Score, beste zuerst.
    """
    if not deals:
        return [
            f"📋 Deal-Bericht {date.today().isoformat()}\n\n"
            "Keine Deals gefunden - entweder gerade nichts reduziert, oder "
            "noch kein frischer Crawl gelaufen."
        ]

    by_category: dict[str, list[Deal]] = defaultdict(list)
    for deal in deals:
        by_category[deal.offer.category or SONSTIGES].append(deal)

    header = (
        f"📋 Deal-Bericht {date.today().isoformat()}\n"
        f"{len(deals)} Deal(s) in {len(by_category)} Kategorie(n) gefunden.\n"
        "Bitte durchsehen und die gewuenschten von Hand in den "
        "WhatsApp-Kanal kopieren."
    )
    chunks = [header]

    for category in sorted(by_category):
        cat_deals = sorted(by_category[category], key=lambda d: d.score, reverse=True)
        shown = cat_deals[:top_per_category]
        lines = [f"📂 {category} ({len(shown)} von {len(cat_deals)} gezeigt)"]
        lines += [f"\n{format_deal(deal)}" for deal in shown]
        chunks.append(_truncate("\n".join(lines)))

    return chunks


def _truncate(text: str) -> str:
    if len(text) <= TELEGRAM_MSG_LIMIT:
        return text
    return text[: TELEGRAM_MSG_LIMIT - 20] + "\n… (gekuerzt)"
