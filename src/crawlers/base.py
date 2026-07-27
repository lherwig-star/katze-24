"""Basisklasse und Registry fuer alle Crawler.

Der Trick: Jede Unterklasse von BaseCrawler traegt sich beim Import
automatisch in REGISTRY ein (__init_subclass__). Dadurch muss niemand eine
zentrale Liste pflegen - ein neuer Crawler ist EINE neue Datei, sonst nichts.

Das ist der Grund, warum ihr euch beim Mergen nie in die Quere kommt:
Finn legt crawlers/fressnapf.py an, Lukas crawlers/zooplus.py. Git sieht
zwei neue Dateien, kein Konflikt. Niemals moeglich, wenn man stattdessen
eine gemeinsame CRAWLERS = [...] Liste pflegt.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections.abc import Iterator
from typing import ClassVar

from src.http import Fetcher
from src.models import Offer

log = logging.getLogger(__name__)

REGISTRY: dict[str, type["BaseCrawler"]] = {}


class BaseCrawler(ABC):
    """Erbt davon, um einen neuen Shop anzubinden.

    Pflicht:
      shop    - eindeutiger Kurzname, taucht so in der DB auf
      crawl() - liefert Offer-Objekte (yield, nicht return einer Liste)

    Optional:
      enabled - auf False setzen, solange der Crawler noch ein Stub ist
      delay   - eigene Pause, falls der Shop empfindlich ist
    """

    shop: ClassVar[str] = ""
    enabled: ClassVar[bool] = True
    delay: ClassVar[tuple[float, float]] = (2.0, 4.0)

    def __init_subclass__(cls, **kwargs) -> None:
        super().__init_subclass__(**kwargs)
        if not cls.shop:
            raise TypeError(
                f"{cls.__name__} braucht ein Klassenattribut 'shop', "
                "z.B. shop = 'fressnapf'"
            )
        if cls.shop in REGISTRY:
            raise ValueError(
                f"Der shop-Name {cls.shop!r} ist schon von "
                f"{REGISTRY[cls.shop].__name__} belegt. Sucht euch einen anderen."
            )
        REGISTRY[cls.shop] = cls

    def __init__(self) -> None:
        self.fetcher = Fetcher(delay=self.delay)

    @abstractmethod
    def crawl(self, limit: int | None = None) -> Iterator[Offer]:
        """Angebote des Shops liefern.

        limit: maximale Anzahl Angebote (fuer schnelle Testlaeufe).
        Bei Fehlern in einzelnen Produkten: loggen und weitermachen,
        nicht den ganzen Lauf abbrechen.
        """
        raise NotImplementedError

    def run(self, limit: int | None = None) -> list[Offer]:
        """crawl() aufrufen und kaputte Eintraege rausfiltern."""
        offers: list[Offer] = []
        for raw in self.crawl(limit=limit):
            offers.append(raw)
            if limit and len(offers) >= limit:
                break
        log.info("%s: %s Angebote", self.shop, len(offers))
        return offers


def get_crawlers(only: str | None = None) -> list[type[BaseCrawler]]:
    """Alle aktiven Crawler, optional gefiltert auf einen Shop."""
    from src import crawlers  # noqa: F401  - loest die Auto-Discovery aus

    found = [c for c in REGISTRY.values() if c.enabled]
    if only:
        found = [c for c in REGISTRY.values() if c.shop == only]
        if not found:
            raise SystemExit(
                f"Kein Crawler fuer {only!r}. Verfuegbar: "
                f"{', '.join(sorted(REGISTRY)) or '(keiner)'}"
            )
    return found
