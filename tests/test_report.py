"""Tests fuer den Kategorie-Bericht (src/report.py)."""

from __future__ import annotations

from src.models import Deal, Offer
from src.report import build_report


def _deal(product_id: str, category: str | None, score: float) -> Deal:
    offer = Offer(
        shop="test", product_id=product_id, title=f"Produkt {product_id}",
        price_cents=999, list_price_cents=1999,
        url=f"https://example.com/p/{product_id}", category=category,
    )
    return Deal(
        offer=offer, ref_price_cents=1999, discount_pct=50.0,
        reason="50% reduziert", score=score,
    )


def test_gruppiert_nach_kategorie():
    deals = [
        _deal("1", "Futter", 50.0),
        _deal("2", "Streu", 30.0),
        _deal("3", "Futter", 70.0),
    ]
    chunks = build_report(deals, top_per_category=5)

    # Kopfzeile + 2 Kategorien (Futter, Streu)
    assert len(chunks) == 3
    futter_chunk = next(c for c in chunks if "📂 Futter" in c)
    assert "Produkt 1" in futter_chunk
    assert "Produkt 3" in futter_chunk
    assert "Streu" not in futter_chunk.split("\n")[0]


def test_top_n_pro_kategorie_begrenzt():
    deals = [_deal(str(i), "Futter", float(i)) for i in range(10)]
    chunks = build_report(deals, top_per_category=3)

    futter_chunk = next(c for c in chunks if "📂 Futter" in c)
    assert "(3 von 10 gezeigt)" in futter_chunk
    # Beste zuerst (hoechster Score = hoechste id hier)
    assert futter_chunk.index("Produkt 9") < futter_chunk.index("Produkt 7")


def test_ohne_kategorie_landet_in_sonstiges():
    deals = [_deal("1", None, 10.0)]
    chunks = build_report(deals)
    assert any("📂 Sonstiges" in c for c in chunks)


def test_keine_deals_liefert_hinweis():
    chunks = build_report([])
    assert len(chunks) == 1
    assert "Keine Deals" in chunks[0]
