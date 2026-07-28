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
  3. wenn Produkte drin sind -> fertig, nie CSS anfassen (Hilfsfunktionen
     dafuer liegen in src/jsonld.py, siehe auch fressnapf.py fuer einen
     Shop mit anderer Verschachtelung)
  4. erst wenn nicht -> CSS-Selektoren (siehe demo_books.py)

robots.txt-Stand: /shop/... ist erlaubt, nur /ov? und /detailedQuestion.htm
sind gesperrt. Crawl-delay 5s gilt laut robots.txt nur fuer bingbot & Co,
wir halten uns trotzdem daran.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterator
from typing import Any

from src.crawlers.base import BaseCrawler
from src.jsonld import find_by_type
from src.models import Offer
from src.parse import clean_title, parse_price, parse_unit

log = logging.getLogger(__name__)

BASE = "https://www.zooplus.de"

# Zurueck auf die normalen Kategorien. Kurzer Exkurs zur gefilterten
# Rabatt-Suche (/search/results?...&filters=...price_reduced): ein echter
# Testlauf (siehe Chat-Verlauf) hat gezeigt, dass diese Seite zwar
# erreichbar ist, aber KEIN Product-JSON-LD im HTML mitliefert (0 Treffer)
# - vermutlich eine reine JS-Facettensuche ohne Server-Rendering, anders
# als /shop/..., das nachweislich SEO-gerendert ist. Zooplus war im
# urspruenglichen Vollkatalog-Crawl mit ~2 Minuten ohnehin nie der
# Flaschenhals (das war Fressnapf mit seinen Einzelabrufen pro Produkt) -
# den funktionierenden Teil aufzugeben, um eine kaputte Seite zu testen,
# war die falsche Abwaegung. Dank paralleler Ausfuehrung (main.py) passt
# Zooplus' Laufzeit ohnehin locker in Fressnapfs laengeres Zeitbudget, die
# Gesamtlaufzeit steigt durch die volle Kategorien-Liste hier kaum.
CATEGORIES = [
    "/shop/katzen/katzenfutter_dose",
    "/shop/katzen/katzenfutter_trockenfutter",
    "/shop/katzen/katzenstreu",
    "/shop/katzen/katzenspielzeug",
]

MAX_PAGES = 5
_ID_RE = re.compile(r"/(\d{4,})(?:\?|$)")


def _page_url(category: str, page: int) -> str:
    """Kategorie-URL um den Seiten-Parameter ergaenzen.

    Die meisten Eintraege in CATEGORIES sind einfache Pfade ohne
    Query-String ("/shop/..."), aber gefilterte Seiten wie eine
    Rabatt-Uebersicht (".../search/results?q=...&filters=...") haben
    schon eines. Ein hartcodiertes "?p=" wuerde dort ein zweites "?" in
    die URL setzen und sie kaputt machen - deshalb hier "&p=" anhaengen,
    wenn schon ein "?" vorhanden ist.
    """
    if page <= 1:
        return f"{BASE}{category}"
    sep = "&" if "?" in category else "?"
    return f"{BASE}{category}{sep}p={page}"


class ZooplusCrawler(BaseCrawler):
    shop = "zooplus"
    delay = (4.0, 6.0)

    def crawl(self, limit: int | None = None) -> Iterator[Offer]:
        count = 0
        seen: set[str] = set()

        for category in CATEGORIES:
            for page in range(1, MAX_PAGES + 1):
                url = _page_url(category, page)
                log.info("%s: %s", self.shop, url)

                try:
                    html = self.fetcher.get(url).text
                except RuntimeError:
                    log.warning("%s: Seite nicht erreichbar: %s", self.shop, url)
                    break

                products = list(find_by_type(html, "Product"))
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

            # KEIN list_price_cents bei Zooplus (mehr): ein echter Testlauf
            # hat gezeigt, dass find_list_price() hier zwar ein Feld findet
            # (bei 674 von 960 Produkten!), das ist aber die dauerhafte UVP,
            # keine zeitlich begrenzte Rabattaktion - Rabatt lag bei 35-43%,
            # also ueber jeder sinnvollen Schwelle, waere also faelschlich
            # als "Deal" durchgegangen. Zooplus scheint dieses Feld einfach
            # immer zu befuellen. list_price_cents soll im ganzen System
            # "echter Referenzpreis fuer einen Deal" bedeuten - hier waere
            # das irrefuehrend. Echte Zooplus-Deals kommen stattdessen ueber
            # den "eigene Historie"-Pfad in dealengine.py, sobald genug
            # taegliche Preispunkte da sind (der volle Katalog-Crawl laeuft
            # ja wieder, siehe Chat-Verlauf).

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
