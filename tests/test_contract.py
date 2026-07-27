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


def test_kein_deal_ohne_shop_markierung(tmp_path):
    """Reiner Preisverfall in unserer eigenen Historie reicht NICHT mehr -
    ausschlaggebend ist, ob der Shop selbst einen Rabatt markiert hat."""
    store = Store(tmp_path / "test.db")
    today = datetime.now(timezone.utc)

    for days_ago in range(30, 0, -1):
        past = Offer(shop="test", product_id="42", title="Testfutter 1 kg",
                     price_cents=1000, url="https://example.com/p/42",
                     seen_at=today - timedelta(days=days_ago))
        store.save_offers([past])

    assert find_deals(store, [_offer(700)]) == []
    store.close()


def test_deal_mit_streichpreis_vom_shop(tmp_path):
    """Der Shop selbst gibt einen Streichpreis an -> das ist der Deal."""
    store = Store(tmp_path / "test.db")
    offer = Offer(shop="test", product_id="99", title="Futter 1 kg",
                  price_cents=1999, list_price_cents=3999,
                  url="https://example.com/p/99")
    deals = find_deals(store, [offer])
    assert len(deals) == 1
    assert deals[0].discount_pct == pytest.approx(50.0, abs=0.1)
    assert "reduziert" in deals[0].reason
    store.close()


def test_deal_ueber_sale_markierung_ohne_zahl(tmp_path):
    """Fressnapf-Sale-Kategorie o.ae.: kein Streichpreis, aber is_marked_down."""
    store = Store(tmp_path / "test.db")
    offer = Offer(shop="test", product_id="100", title="Spielzeug",
                  price_cents=999, is_marked_down=True,
                  url="https://example.com/p/100")
    deals = find_deals(store, [offer])
    assert len(deals) == 1
    assert deals[0].discount_pct == 0.0
    assert "reduziert markiert" in deals[0].reason
    store.close()


def test_historie_ist_nur_noch_zusatzinfo(tmp_path):
    """Ein shop-markierter Deal, der zugleich Tiefstpreis ist, bekommt den
    Hinweis in der Begruendung und einen Score-Bonus - Historie ist aber
    nicht mehr Voraussetzung fuer den Deal selbst."""
    store = Store(tmp_path / "test.db")
    today = datetime.now(timezone.utc)
    for days_ago in range(30, 0, -1):
        past = Offer(shop="test", product_id="42", title="Testfutter 1 kg",
                     price_cents=1000, url="https://example.com/p/42",
                     seen_at=today - timedelta(days=days_ago))
        store.save_offers([past])

    offer = Offer(shop="test", product_id="42", title="Testfutter 1 kg",
                  price_cents=700, list_price_cents=1000,
                  url="https://example.com/p/42")
    deals = find_deals(store, [offer])
    assert len(deals) == 1
    assert deals[0].is_all_time_low
    assert "Tiefstpreis" in deals[0].reason
    store.close()
