"""Tests fuer format_deal - vor allem die rechtlichen Pflichtangaben.

Kein Netzwerkzugriff noetig, reine Stringpruefung.
"""

from datetime import datetime, timezone

from src.models import Deal, Offer
from src.notifier import affiliate_url, format_deal


def _deal() -> Deal:
    offer = Offer(
        shop="test", product_id="1", title="Testfutter 1 kg",
        price_cents=1369, url="https://example.com/p/1",
        unit_amount=1.0, unit="kg",
        seen_at=datetime(2026, 7, 27, 20, 46, tzinfo=timezone.utc),
    )
    return Deal(
        offer=offer, ref_price_cents=1899, discount_pct=27.9,
        reason="Testgrund", score=27.9,
    )


def test_werbekennzeichnung_ist_erste_zeile():
    text = format_deal(_deal())
    assert text.startswith("Werbung\n")


def test_zeitstempel_ist_enthalten():
    text = format_deal(_deal())
    assert "27.07.2026 20:46 UTC" in text


def test_affiliate_url_ist_aktuell_passthrough():
    assert affiliate_url("https://example.com/p/1") == "https://example.com/p/1"
