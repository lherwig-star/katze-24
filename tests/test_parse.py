"""Tests fuer die Parser. Hier gehoert jedes komische Preisformat rein,
das euch beim Crawlen begegnet - erst Test, dann Fix."""

import pytest

from src.parse import clean_title, parse_price, parse_unit


@pytest.mark.parametrize(
    "text,expected",
    [
        ("13,69 €", 1369),
        ("€ 13,69", 1369),
        ("1.234,56 EUR", 123456),
        ("13.69", 1369),
        ("9 €", 900),
        ("ab 4,99 €", 499),
        ("", None),
        ("kein Preis", None),
    ],
)
def test_parse_price(text, expected):
    assert parse_price(text) == expected


@pytest.mark.parametrize(
    "text,expected",
    [
        ("animonda Carny Adult 6 x 800 g", (4.8, "kg")),
        ("Whiskas 12x85g Ragout", (1.02, "kg")),
        ("Katzenstreu 1,5 kg", (1.5, "kg")),
        ("Trinkbrunnen 2 x 400 ml", (0.8, "l")),
        ("Spielmaus 6 Stk.", (6.0, "stk")),
        ("Kratzbaum Deluxe", None),
    ],
)
def test_parse_unit(text, expected):
    assert parse_unit(text) == expected


def test_clean_title():
    assert clean_title("  Whiskas\n\t  Ragout  ") == "Whiskas Ragout"
