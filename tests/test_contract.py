"""Vertragstests: gelten fuer JEDEN Crawler, den ihr baut.

Wenn einer von euch einen Crawler kaputt macht, faellt es hier auf -
bevor der PR gemergt wird. Kein Netzwerkzugriff, laeuft in Sekunden.
"""

from datetime import datetime, timedelta, timezone

import pytest

from src.crawlers import REGISTRY, get_crawlers
from src.dealengine import find_deals
from src.models import Offer
from src.storage import Store


def test_crawler_gefunden():
    get_crawlers()
    assert REGISTRY, "Auto-Discovery hat keinen Crawler gefunden"


@pytest.mark.parametrize("shop", sorted(REGISTRY))
def test_crawler_vertrag(shop):
    cls = REGISTRY[shop]
    assert cls.shop == shop
    assert isinstance(cls.enabled, bool)
    assert hasattr(cls, "crawl")


def test_offer_validierung():
    with pytest.raises(ValueError):
        Offer(shop="x", product_id="1", title="t", price_cents=0,
              url="https://a.de")
    with pytest.raises(ValueError):
        Offer(shop="x", product_id="1", title="t", price_cents=100, url="/relativ")


def test_grundpreis():
    offer = Offer(shop="x", product_id="1", title="t", price_cents=1000,
                  url="https://a.de", unit_amount=2.0, unit="kg")
    assert offer.price_per_unit_cents == 500


def _offer(price: int) -> Offer:
    return Offer(shop="test", product_id="42", title="Testfutter 1 kg",
                 price_cents=price, url="https://example.com/p/42",
                 unit_amount=1.0, unit="kg")


def test_deal_erkennung_gegen_historie(tmp_path):
    """Preis faellt von konstant 10 EUR auf 7 EUR -> muss ein Deal sein."""
    store = Store(tmp_path / "test.db")
    today = datetime.now(timezone.utc)

    for days_ago in range(30, 0, -1):
        past = Offer(shop="test", product_id="42", title="Testfutter 1 kg",
                     price_cents=1000, url="https://example.com/p/42",
                     seen_at=today - timedelta(days=days_ago))
        store.save_offers([past])

    deals = find_deals(store, [_offer(700)])
    assert len(deals) == 1
    assert deals[0].is_all_time_low
    assert deals[0].discount_pct == pytest.approx(30.0)
    store.close()


def test_kein_deal_ohne_historie(tmp_path):
    """Ohne Historie und ohne Streichpreis darf nichts gemeldet werden."""
    store = Store(tmp_path / "test.db")
    assert find_deals(store, [_offer(700)]) == []
    store.close()


def test_gefaketer_streichpreis_wird_abgewertet(tmp_path):
    """Streichpreis-Deals bekommen einen niedrigeren Score als echte."""
    store = Store(tmp_path / "test.db")
    offer = Offer(shop="test", product_id="99", title="Fake 1 kg",
                  price_cents=1999, list_price_cents=3999,
                  url="https://example.com/p/99")
    deals = find_deals(store, [offer])
    assert len(deals) == 1
    assert "Streichpreis" in deals[0].reason
    assert deals[0].score < deals[0].discount_pct
    store.close()


def test_kleiner_streichpreis_rabatt_zaehlt(tmp_path):
    """Auch ein moderater, vom Shop markierter Rabatt (15%) muss zaehlen -
    die Schwelle ist bewusst auf 10% gesenkt, weil hier nicht bewertet
    wird, ob der Rabatt "echt" ist, sondern nur, ob der Shop ihn markiert."""
    store = Store(tmp_path / "test.db")
    offer = Offer(shop="test", product_id="15", title="Kleiner Rabatt 1 kg",
                  price_cents=850, list_price_cents=1000,
                  url="https://example.com/p/15")
    deals = find_deals(store, [offer])
    assert len(deals) == 1
    store.close()
