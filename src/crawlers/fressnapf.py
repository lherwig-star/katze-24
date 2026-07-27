"""Crawler fuer fressnapf.de  --  STUB, hier ist noch nichts implementiert.

Das ist die Uebungsaufgabe fuer den, der sich Fressnapf schnappt.
Solange enabled = False steht, wird der Crawler nirgends aufgerufen -
ihr koennt also gefahrlos committen, auch wenn er noch nicht laeuft.

SO GEHT IHR VOR
---------------
1. robots.txt lesen (Stand der Voranalyse):
     erlaubt:   Kategorieseiten unter /shop/...
     GESPERRT:  */search, */cart/, */checkout, *sort=*, *viewtype=*
   -> Also ueber Kategorieseiten gehen, NICHT ueber die Suche.
   -> https://www.fressnapf.de/sitemap.xml listet alle Kategorien.

2. Eine Kategorieseite runterladen und nachsehen, ob JSON-LD drin ist:

     curl -sL -A "Mozilla/5.0" "https://www.fressnapf.de/c/katze/katzenfutter/" \
       -o fn.html
     grep -c 'application/ld+json' fn.html
     grep -o '"@type":"Product"' fn.html | wc -l

   Wenn da Produkte drinstehen: den Parser aus zooplus.py kopieren,
   `_walk_products` ist absichtlich generisch geschrieben.

3. Wenn KEIN JSON-LD da ist, zwei Moeglichkeiten:
   a) Die Seite rendert per JavaScript nach. Dann im Browser die
      Netzwerk-Konsole oeffnen (F12 -> Network -> Fetch/XHR) und schauen,
      welche JSON-API die Produktliste liefert. Diese API direkt abfragen
      ist einfacher UND schonender als HTML zu parsen.
      Hinweis: robots.txt erlaubt /api/proxy/v1/* ausdruecklich.
   b) Reines Server-HTML -> CSS-Selektoren wie in demo_books.py.

4. enabled = True setzen, wenn `python -m src.main crawl --shop fressnapf
   --limit 5` sinnvolle Ergebnisse liefert.

WORAUF ACHTEN
-------------
- product_id muss stabil sein. Nimm die Artikelnummer aus der URL, nicht
  die Position in der Liste - sonst ist die Preishistorie wertlos.
- Preise immer in Cent (parse_price nutzt).
- Einzelne kaputte Produkte ueberspringen, nicht den Lauf abbrechen.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator

from src.crawlers.base import BaseCrawler
from src.models import Offer

log = logging.getLogger(__name__)

BASE = "https://www.fressnapf.de"

CATEGORIES = [
    "/c/katze/katzenfutter/",
    "/c/katze/katzenstreu/",
    "/c/katze/katzenspielzeug/",
]


class FressnapfCrawler(BaseCrawler):
    shop = "fressnapf"
    enabled = False  # <- auf True, sobald crawl() echte Daten liefert
    delay = (4.0, 6.0)

    def crawl(self, limit: int | None = None) -> Iterator[Offer]:
        raise NotImplementedError(
            "Fressnapf-Crawler ist noch nicht gebaut - siehe Anleitung "
            "oben in src/crawlers/fressnapf.py"
        )
        yield  # macht die Funktion zum Generator (unerreichbar, aber noetig)
