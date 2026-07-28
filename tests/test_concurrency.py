"""Tests fuer die Parallelisierung in src/main.py::_crawl_all.

Kein Netzwerkzugriff - Fake-Crawler mit time.sleep() statt echten Requests.
"""

import time

from src.main import _crawl_all


class _FakeCrawler:
    """Duck-typed wie BaseCrawler (nur .shop und .run() noetig)."""

    def __init__(self, shop, sleep_s=0.0, offers=None, raise_exc=None):
        self.shop = shop
        self.sleep_s = sleep_s
        self._offers = offers or []
        self._raise_exc = raise_exc

    def run(self, limit=None):
        time.sleep(self.sleep_s)
        if self._raise_exc:
            raise self._raise_exc
        return list(self._offers)


def test_shops_laufen_parallel_nicht_nacheinander():
    """Zwei 0,2s-Crawler zusammen duerfen nicht ~0,4s (Summe) brauchen,
    sondern nur ~0,2s (Maximum) - das ist der Sinn der Parallelisierung."""
    crawlers = [_FakeCrawler("a", sleep_s=0.2), _FakeCrawler("b", sleep_s=0.2)]
    start = time.monotonic()
    _crawl_all(crawlers, limit=None)
    elapsed = time.monotonic() - start
    assert elapsed < 0.35


def test_abgestuerzter_crawler_reisst_die_anderen_nicht_mit():
    ok = _FakeCrawler("ok", offers=["angebot"])
    broken = _FakeCrawler("broken", raise_exc=RuntimeError("kaputt"))
    results = _crawl_all([ok, broken], limit=None)
    assert results[ok] == ["angebot"]
    assert results[broken] == []
