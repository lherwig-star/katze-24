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

RABATT-ERKENNUNG - ZWEITER ANLAUF (wichtige Korrektur nach Live-Test):
Die Kategorieseite liefert im JSON-LD ein Feld "ListPrice" neben "SalePrice".
Erster Versuch: das als Streichpreis genommen - Live-Test zeigte aber, dass
das bei fast JEDEM Multipack gesetzt ist (29 von 30 Testprodukten!), weil es
der staendige "Einzelpreis vs. Grosspackung"-Vergleich ist, kein zeitlich
begrenzter Rabatt. Damit waere praktisch der ganze Katalog "reduziert".

Die eigene Produktseite (nicht die Kategorieseite!) hat dagegen ein
eigenstaendiges, selteneres Feld:
    "priceSpecification": [
        {"priceType": "https://schema.org/StrikethroughPrice", "price": 4.99},
        {"priceType": "https://schema.org/SalePrice", "price": 4.24}
    ]
StrikethroughPrice taucht nur auf, wenn GERADE ein echter, zeitlich
begrenzter Rabatt aktiv ist (getestet: baugleiches Produkt ohne aktuellen
Rabatt hat in seinen anderen Varianten nur SalePrice, keine
StrikethroughPrice). Deshalb zweistufig wie bei Fressnapf: Kategorieseite
fuer die Grunddaten, zusaetzlich JEDE Produktseite fuer den echten
Rabatt-Status. Kostet ca. 3x mehr Requests, ist dafuer nicht durch
Mengenrabatt-Rauschen verfaelscht.
"""

from __future__ import annotations

import dataclasses
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
                    yield self._enrich_with_discount(offer)
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

            # KEIN list_price_cents aus der Kategorieseite: ein echter
            # Testlauf hat gezeigt, dass das dortige Feld bei 674 von 960
            # Produkten gesetzt ist - das ist die dauerhafte UVP, keine
            # zeitlich begrenzte Rabattaktion (Rabatt lag bei 35-43%, also
            # ueber jeder sinnvollen Schwelle). Der echte Rabatt-Status kommt
            # stattdessen aus _enrich_with_discount() weiter unten, das dafuer
            # extra die Produktseite abruft (siehe Docstring oben,
            # "RABATT-ERKENNUNG - ZWEITER ANLAUF").

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

    def _enrich_with_discount(self, offer: Offer) -> Offer:
        """Produktseite abrufen und den ECHTEN aktuellen Preis + Rabatt-Status
        uebernehmen. Noetig, weil die Kategorieseite manchmal noch den Preis
        VOR einem gerade aktiven Rabatt zeigt (beobachtet: Kategorie zeigte
        13,69 EUR, die Produktseite fuer dieselbe Variante hatte SalePrice
        12,32 EUR + StrikethroughPrice 13,69 EUR - die Kategorieseite haette
        uns also faelschlich "kein Rabatt" vorgegaukelt). Die Produktseite
        ist die naehere Quelle zur Kasse und gilt deshalb als massgeblich.

        Liefert bei Fehlern das unveraenderte Angebot zurueck.
        """
        try:
            html = self.fetcher.get(offer.url).text
        except RuntimeError:
            log.warning("%s: Produktseite fuer Rabatt-Check nicht erreichbar: %s",
                        self.shop, offer.url)
            return offer

        prices = _extract_variant_prices(html, offer.url)
        if prices is None:
            return offer
        sale_cents, strikethrough_cents = prices

        updates: dict[str, Any] = {}
        if sale_cents:
            updates["price_cents"] = sale_cents
        # StrikethroughPrice steht auch bei NICHT reduzierten Varianten im
        # Feld, dann aber gleich dem SalePrice - erst ein echter Unterschied
        # zaehlt als Rabatt.
        if strikethrough_cents and sale_cents and strikethrough_cents > sale_cents:
            updates["list_price_cents"] = strikethrough_cents
            updates["is_marked_down"] = True

        return dataclasses.replace(offer, **updates) if updates else offer


def _extract_variant_prices(
    html: str, target_url: str
) -> tuple[int | None, int | None] | None:
    """(SalePrice, StrikethroughPrice) in Cent fuer genau die Variante, die
    zu target_url passt (eine Produktseite listet mehrere Varianten mit je
    eigener offers.url). None, wenn die Variante nicht gefunden wurde."""
    for product in find_by_type(html, "Product"):
        offers = product.get("offers") or {}
        if isinstance(offers, list):
            offers = offers[0] if offers else {}
        if offers.get("url") != target_url:
            continue

        sale_cents: int | None = None
        strikethrough_cents: int | None = None
        specs = offers.get("priceSpecification") or []
        if isinstance(specs, dict):
            specs = [specs]
        for spec in specs:
            if not isinstance(spec, dict):
                continue
            price_type = str(spec.get("priceType", ""))
            price = parse_price(str(spec.get("price", "")))
            if "StrikethroughPrice" in price_type:
                strikethrough_cents = price
            elif "SalePrice" in price_type:
                sale_cents = price
        return sale_cents, strikethrough_cents
    return None
