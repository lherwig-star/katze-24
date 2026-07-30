"""Tests fuer die Deal-Karten (src/cards.py).

Bewusst ohne image_url getestet - kein Netzwerkzugriff in Tests (siehe
CLAUDE.md). Der Bildpfad (echtes Produktfoto laden) ist manuell gegen
echte Crawl-Daten getestet, siehe PR-Beschreibung.
"""

from __future__ import annotations

from PIL import Image

from src.cards import SIZE, build_card, save_cards
from src.models import Deal, Offer


def _deal(**kwargs) -> Deal:
    defaults = dict(
        shop="test", product_id="1", title="Testfutter Adult 12 x 100 g",
        price_cents=999, list_price_cents=1499,
        url="https://example.com/p/1", category="Futter",
        unit_amount=1.2, unit="kg",
    )
    defaults.update(kwargs)
    offer = Offer(**defaults)
    return Deal(
        offer=offer, ref_price_cents=1499, discount_pct=33.4,
        reason="33% reduziert (statt 14,99 EUR)", score=33.4,
    )


def test_karte_hat_richtige_groesse():
    img = build_card(_deal())
    assert isinstance(img, Image.Image)
    assert img.size == (SIZE, SIZE)


def test_karte_ohne_bild_nutzt_platzhalter():
    """Kein image_url -> darf nicht crashen, liefert trotzdem eine Karte."""
    img = build_card(_deal(image_url=None))
    assert img.size == (SIZE, SIZE)


def test_karte_ohne_exakten_rabatt():
    """is_marked_down ohne list_price_cents (z.B. Fressnapf-Sale) -> kein
    Kreis mit Prozentzahl, aber trotzdem eine gueltige Karte."""
    offer = Offer(
        shop="test", product_id="2", title="Spielzeug", price_cents=999,
        url="https://example.com/p/2", is_marked_down=True, image_url=None,
    )
    deal = Deal(offer=offer, ref_price_cents=999, discount_pct=0.0,
                reason="vom Shop als reduziert markiert", score=0.0)
    img = build_card(deal)
    assert img.size == (SIZE, SIZE)


def test_langer_titel_wird_umgebrochen_ohne_crash():
    long_title = "Ein wirklich sehr langer Produktname " * 4
    img = build_card(_deal(title=long_title.strip()))
    assert img.size == (SIZE, SIZE)


def test_save_cards_schreibt_dateien(tmp_path):
    deals = [_deal(product_id=str(i), image_url=None) for i in range(3)]
    paths = save_cards(deals, tmp_path, limit=2)
    assert len(paths) == 2
    for p in paths:
        assert p.exists()
        assert p.suffix == ".png"
