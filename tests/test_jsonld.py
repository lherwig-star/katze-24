"""Tests fuer die JSON-LD-Hilfsfunktionen, insbesondere find_list_price.

Kein Netzwerkzugriff - die Fixtures hier sind von Hand nach dem
schema.org-Standard gebaut (StrikethroughPrice-priceType), nicht aus einem
echten Crawl kopiert. zooplus.de und fressnapf.de blocken Requests aus
dieser Umgebung (403), das Feld ist also bisher NICHT gegen die echten
Shop-Seiten verifiziert - das zeigt erst der naechste echte Crawl-Lauf.
"""

from src.jsonld import find_list_price


def test_find_list_price_strikethrough():
    offers = {
        "price": "13.69",
        "priceSpecification": [
            {"priceType": "https://schema.org/StrikethroughPrice", "price": "18.99"},
        ],
    }
    assert find_list_price(offers) == "18.99"


def test_find_list_price_ohne_spezifikation():
    offers = {"price": "13.69"}
    assert find_list_price(offers) is None


def test_find_list_price_als_liste():
    offers = [{
        "price": "13.69",
        "priceSpecification": {"priceType": "ListPrice", "price": "16.49"},
    }]
    assert find_list_price(offers) == "16.49"


def test_find_list_price_andere_price_types_werden_ignoriert():
    offers = {
        "price": "13.69",
        "priceSpecification": [
            {"priceType": "https://schema.org/RegularPrice", "price": "13.69"},
        ],
    }
    assert find_list_price(offers) is None
