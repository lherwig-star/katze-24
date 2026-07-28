"""Crawler fuer fressnapf.de.

RECHERCHEERGEBNIS (so kam die Loesung zustande - nuetzlich als Vorlage
fuer den naechsten Shop):

  1. robots.txt geprueft: /c/... (Kategorien) und /p/... (Produkte) sind
     erlaubt. Gesperrt: /s/, */search, *sort=*, *viewtype=*, */cart/ etc.

  2. Kategorieseite (/c/katze/katzenfutter/) mit curl geladen: kein
     Product-JSON-LD, dafuer ein ItemList mit Titel+URL+Bild fuer die
     ersten ~49 Produkte (SSR fuer SEO). window.__NUXT__ ist leer -
     die Seite ist eine Nuxt3-SPA, die Preise erst per JS aus einer
     internen API nachlaedt.

  3. Diese interne API (/api/proxy/v1/product/search, sichtbar im JS-Bundle)
     haben wir NICHT reverse-engineered: sie verlangt ein eigenes,
     undokumentiertes POST-Body-Format gegen ein privates Backend. Das
     waere Rätselraten gegen fremde interne Schnittstellen - genau das
     vermeiden wir laut CLAUDE.md.

  4. Stattdessen: jede einzelne Produktseite (/p/.../<id>/) hat IHR EIGENES
     vollstaendiges JSON-LD mit Preis, Marke, SKU, Verfuegbarkeit - vermutlich
     weil Produktseiten fuer Google Rich Snippets separat vorgerendert werden.

DAHER DER ZWEISTUFIGE ABLAUF:
  Kategorieseite -> Liste von Produkt-URLs (via ItemList-JSON-LD)
  -> jede Produktseite einzeln abrufen -> Product-JSON-LD (wie bei Zooplus)

Das kostet mehr Requests als bei Zooplus, ist aber genauso stabil und
robots.txt-konform.

GRENZE: Kein ?page=2-Parameter aendert die SSR-Liste - sie ist fix auf die
ersten ~49 Produkte pro Kategorie begrenzt (der Rest kommt nur per JS-
Pagination, die wir nicht mitmachen). Fuer mehr Abdeckung: weitere
Unterkategorien in CATEGORIES ergaenzen, z.B. nach Marke gefiltert.

RABATT-ERKENNUNG: Anders als Zooplus hat Fressnapf keinen Streichpreis im
Produkt-JSON-LD. Es gibt aber eine eigene Sale-Kategorie (/c/katze/sale/),
in der der Shop selbst festlegt, was reduziert ist - genau das SALE_CATEGORY
liefert, mit is_marked_down=True markiert (siehe dealengine.py). Die
Sale-Kategorie wird bewusst ZUERST gecrawlt, damit ein Produkt, das in
beiden Listen auftaucht, seine Markierung behaelt (Dedup ueber `seen`).
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterator

from src.crawlers.base import BaseCrawler
from src.jsonld import find_by_type
from src.models import Offer
from src.parse import clean_title, parse_price, parse_unit

log = logging.getLogger(__name__)

BASE = "https://www.fressnapf.de"

SALE_CATEGORY = "/c/katze/sale/"

# (Pfad, Label fuers Berichts-Gruppieren)
CATEGORIES = [
    ("/c/katze/katzenfutter/", "Futter"),
    ("/c/katze/hygiene-pflege/katzenstreu/", "Streu"),  # Fressnapf hat
    # umstrukturiert, alter Pfad /c/katze/katzenstreu/ gibt inzwischen 404
    # (im Cloud-Crawl vom 27.07. aufgefallen: 3 Fehlversuche, Kategorie
    # wurde uebersprungen)
    ("/c/katze/katzenspielzeug/", "Spielzeug"),
]

_ID_RE = re.compile(r"-(\d+)/?$")


class FressnapfCrawler(BaseCrawler):
    shop = "fressnapf"
    delay = (3.0, 5.0)

    def crawl(self, limit: int | None = None) -> Iterator[Offer]:
        count = 0
        seen: set[str] = set()

        # Sale-Kategorie zuerst, damit ihre is_marked_down=True-Markierung
        # gewinnt, falls ein Produkt auch in einer normalen Kategorie steht.
        # Sale mischt alle Warengruppen - category bleibt dort None (siehe
        # report.py: solche Angebote landen im Bericht unter "Sonstiges").
        categories = [(SALE_CATEGORY, None, True)] + [
            (path, label, False) for path, label in CATEGORIES
        ]

        for category, label, is_sale in categories:
            url = f"{BASE}{category}"
            log.info("%s: Kategorie %s%s", self.shop, url, " (Sale)" if is_sale else "")
            try:
                html = self.fetcher.get(url).text
            except RuntimeError:
                log.warning("%s: Kategorie nicht erreichbar: %s", self.shop, url)
                continue

            for item in find_by_type(html, "ListItem"):
                product_url = item.get("url")
                # Die Breadcrumb-Navigation ("Startseite > Katze > ...") ist
                # ebenfalls ein ListItem, nutzt aber das Feld "item" statt
                # "url" - so werden Produkte automatisch sauber getrennt.
                if not product_url or "/p/" not in product_url:
                    continue
                if product_url in seen:
                    continue
                seen.add(product_url)

                offer = self._fetch_product(
                    product_url, category=label, is_marked_down=is_sale
                )
                if offer is None:
                    continue
                yield offer
                count += 1
                if limit and count >= limit:
                    return

    def _fetch_product(
        self, url: str, category: str | None = None, is_marked_down: bool = False
    ) -> Offer | None:
        try:
            html = self.fetcher.get(url).text
        except RuntimeError:
            log.warning("%s: Produktseite nicht erreichbar: %s", self.shop, url)
            return None

        for product in find_by_type(html, "Product"):
            return self._to_offer(product, url, category, is_marked_down)
        log.debug("%s: kein Product-JSON-LD auf %s", self.shop, url)
        return None

    def _to_offer(
        self, product: dict, url: str, category: str | None = None,
        is_marked_down: bool = False,
    ) -> Offer | None:
        try:
            offers = product.get("offers") or {}
            if isinstance(offers, list):
                offers = offers[0] if offers else {}

            title = clean_title(product.get("name", ""))
            price_cents = parse_price(str(offers.get("price", "")))
            if not (title and price_cents):
                return None

            sku = product.get("sku")
            match = _ID_RE.search(url.rstrip("/"))
            product_id = str(sku) if sku else (
                match.group(1) if match else url.rstrip("/").rsplit("/", 1)[-1]
            )

            brand = product.get("brand") or {}
            brand_name = brand.get("name") if isinstance(brand, dict) else brand

            image = product.get("image")
            if isinstance(image, list):
                image = image[0] if image else None

            availability = str(offers.get("availability", "")).lower()
            amount_unit = parse_unit(title)

            return Offer(
                shop=self.shop,
                product_id=product_id,
                title=title,
                price_cents=price_cents,
                url=url,
                brand=brand_name,
                is_marked_down=is_marked_down,
                category=category,
                image_url=image,
                available="instock" in availability.replace("_", ""),
                unit_amount=amount_unit[0] if amount_unit else None,
                unit=amount_unit[1] if amount_unit else None,
            )
        except Exception:
            log.exception("%s: Produkt nicht konvertierbar: %s", self.shop, url)
            return None
