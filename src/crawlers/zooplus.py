"""Crawler fuer zooplus.de.

Wichtigste Erkenntnis aus der Voranalyse: Zooplus liefert die komplette
Produktliste als JSON-LD (schema.org) im HTML mit. Wir brauchen also KEINE
CSS-Selektoren fuer die Produktdaten.

Warum das viel besser ist:
  - JSON-LD ist fuer Google gedacht. Shops aendern es fast nie, weil sonst
    ihr SEO leidet. CSS-Klassen aendern sich bei jedem Redesign.
  - Die Struktur ist standardisiert (schema.org/Product), d.h. derselbe
    Parser funktioniert bei vielen anderen Shops auch.

Faustregel fuer jeden neuen Shop, den ihr anbindet:
  1. Seite mit curl laden
  2. nach 'application/ld+json' greppen
  3. wenn Produkte drin sind -> fertig, nie CSS anfassen
  4. erst wenn nicht -> CSS-Selektoren (siehe demo_books.py)

robots.txt-Stand: /shop/... ist erlaubt, nur /ov? und /detailedQuestion.htm
sind gesperrt. Crawl-delay 5s gilt laut robots.txt nur fuer bingbot & Co,
wir halten uns trotzdem daran.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterator
from typing import Any

from src.crawlers.base import BaseCrawler
from src.models import Offer
from src.parse import clean_title, parse_price, parse_unit

log = logging.getLogger(__name__)

BASE = "https://www.zooplus.de"

# Startpunkte. Hier koennt ihr beliebig erweitern - Katzenfutter, Zubehoer,
# Spielzeug. Die URLs findet ihr, indem ihr auf zooplus.de durch die
# Kategorien klickt und den Pfad kopiert.
CATEGORIES = [
    "/shop/katzen/katzenfutter_dose",
    "/shop/katzen/katzenfutter_trockenfutter",
    "/shop/katzen/katzenstreu",
    "/shop/katzen/katzenspielzeug",
]

MAX_PAGES = 5
_LD_RE = re.compile(
    r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.S | re.I,
)
_ID_RE = re.compile(r"/(\d{4,})(?:\?|$)")


class ZooplusCrawler(BaseCrawler):
    shop = "zooplus"
    delay = (4.0, 6.0)

    def crawl(self, limit: int | None = None) -> Iterator[Offer]:
        count = 0
        seen: set[str] = set()

        for category in CATEGORIES:
            for page in range(1, MAX_PAGES + 1):
                url = f"{BASE}{category}" + (f"?p={page}" if page > 1 else "")
                log.info("%s: %s", self.shop, url)

                try:
                    html = self.fetcher.get(url).text
                except RuntimeError:
                    log.warning("%s: Seite nicht erreichbar: %s", self.shop, url)
                    break

                products = list(self._extract_products(html))
                if not products:
                    log.info("%s: keine Produkte mehr auf %s", self.shop, url)
                    break

                new_on_page = 0
                for raw in products:
                    offer = self._to_offer(raw)
                    if offer is None or offer.uid in seen:
                        continue
                    seen.add(offer.uid)
                    new_on_page += 1
                    yield offer
                    count += 1
                    if limit and count >= limit:
                        return

                # Zooplus liefert bei zu hoher Seitenzahl einfach wieder
                # Seite 1 aus - deshalb hier abbrechen statt endlos zu laufen.
                if new_on_page == 0:
                    break

    def _extract_products(self, html: str) -> Iterator[dict[str, Any]]:
        """Alle schema.org/Product-Objekte aus dem JSON-LD ziehen.

        Zooplus verschachtelt sie als:
          {"mainEntity": {"@type": "ItemList",
                          "itemListElement": [{"item": {...Product...}}]}}
        """
        for block in _LD_RE.findall(html):
            try:
                data = json.loads(block)
            except json.JSONDecodeError:
                log.debug("%s: JSON-LD nicht parsebar", self.shop)
                continue
            yield from _walk_products(data)

    def _to_offer(self, product: dict[str, Any]) -> Offer | None:
        try:
            offers = product.get("offers") or {}
            if isinstance(offers, list):
                offers = offers[0] if offers else {}

            url = offers.get("url") or product.get("url")
            price_raw = offers.get("price")
            title = clean_title(product.get("name", ""))
            if not (url and price_raw and title):
                return None

            price_cents = parse_price(str(price_raw))
            if price_cents is None:
                return None

            match = _ID_RE.search(url.split("?")[0])
            variant = re.search(r"activeVariant=([\d.]+)", url)
            product_id = variant.group(1) if variant else (
                match.group(1) if match else url.rsplit("/", 1)[-1]
            )

            brand = product.get("brand") or {}
            brand_name = brand.get("name") if isinstance(brand, dict) else brand
            if isinstance(brand_name, list):
                brand_name = brand_name[0] if brand_name else None

            image = product.get("image")
            if isinstance(image, list):
                image = image[0] if image else None

            availability = str(offers.get("availability", "")).lower()
            amount_unit = parse_unit(title)

            return Offer(
                shop=self.shop,
                product_id=str(product_id),
                title=title,
                price_cents=price_cents,
                url=url if url.startswith("http") else BASE + url,
                brand=brand_name,
                image_url=image,
                available="instock" in availability.replace("_", ""),
                unit_amount=amount_unit[0] if amount_unit else None,
                unit=amount_unit[1] if amount_unit else None,
            )
        except Exception:
            log.exception("%s: Produkt nicht konvertierbar", self.shop)
            return None


def _walk_products(node: Any) -> Iterator[dict[str, Any]]:
    """Rekursiv durch beliebig verschachteltes JSON-LD nach Products suchen.

    Bewusst generisch: so funktioniert die Funktion auch, wenn Zooplus die
    Verschachtelung aendert - oder wenn ihr sie fuer einen anderen Shop
    wiederverwendet.
    """
    if isinstance(node, dict):
        if node.get("@type") == "Product":
            yield node
        for value in node.values():
            yield from _walk_products(value)
    elif isinstance(node, list):
        for item in node:
            yield from _walk_products(item)
