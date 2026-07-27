"""Referenz-Crawler gegen books.toscrape.com.

Diese Seite existiert ausdruecklich zum Ueben von Scraping - sie hat keinen
Bot-Schutz und aendert sich nicht. Nutzt sie als Vorlage und zum Testen der
Pipeline, wenn ihr gerade keinen echten Shop anfassen wollt.

Lest diese Datei einmal komplett durch, bevor ihr euren eigenen Crawler baut.
Sie zeigt alles, was ein Crawler koennen muss:
  - seitenweise durchlaufen
  - pro Produkt die Felder rausziehen
  - relative Links absolut machen
  - Fehler in einzelnen Produkten ueberspringen statt abzustuerzen
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from urllib.parse import urljoin

from src.crawlers.base import BaseCrawler
from src.models import Offer
from src.parse import clean_title, parse_price, parse_unit

log = logging.getLogger(__name__)

BASE_URL = "https://books.toscrape.com/catalogue/"
PAGE_URL = BASE_URL + "page-{page}.html"
MAX_PAGES = 3


class DemoBooksCrawler(BaseCrawler):
    shop = "demo_books"
    delay = (0.5, 1.0)  # Uebungsseite, darf schneller

    def crawl(self, limit: int | None = None) -> Iterator[Offer]:
        count = 0
        for page in range(1, MAX_PAGES + 1):
            url = PAGE_URL.format(page=page)
            log.info("%s: lade Seite %s", self.shop, page)
            soup = self.fetcher.soup(url)

            cards = soup.select("article.product_pod")
            if not cards:
                log.warning("%s: keine Produkte auf %s - Selektor kaputt?",
                            self.shop, url)
                return

            for card in cards:
                offer = self._parse_card(card)
                if offer is None:
                    continue
                yield offer
                count += 1
                if limit and count >= limit:
                    return

    def _parse_card(self, card) -> Offer | None:
        """Ein Produkt-Kaertchen -> Offer. None, wenn was fehlt."""
        try:
            link = card.select_one("h3 a")
            price_el = card.select_one("p.price_color")
            if link is None or price_el is None:
                return None

            href = urljoin(BASE_URL, link["href"])
            # Slug als stabile ID: ".../a-light-in-the-attic_1000/index.html"
            product_id = href.rstrip("/").split("/")[-2]

            title = clean_title(link.get("title") or link.get_text())
            price_cents = parse_price(price_el.get_text())
            if price_cents is None:
                log.debug("%s: Preis nicht lesbar bei %s", self.shop, title)
                return None

            stock = card.select_one("p.instock.availability")
            available = bool(stock and "in stock" in stock.get_text().lower())

            amount_unit = parse_unit(title)  # bei Buechern meist None

            return Offer(
                shop=self.shop,
                product_id=product_id,
                title=title,
                price_cents=price_cents,
                url=href,
                available=available,
                unit_amount=amount_unit[0] if amount_unit else None,
                unit=amount_unit[1] if amount_unit else None,
            )
        except Exception:
            log.exception("%s: Produkt konnte nicht geparst werden", self.shop)
            return None
