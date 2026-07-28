"""Tests fuer zooplus-spezifische Hilfsfunktionen. Kein Netzwerkzugriff."""

from src.crawlers.zooplus import _page_url


def test_page_url_erste_seite_ohne_parameter():
    assert _page_url("/shop/katzen/katzenfutter_dose", 1) == (
        "https://www.zooplus.de/shop/katzen/katzenfutter_dose"
    )


def test_page_url_einfache_kategorie_ab_seite_2():
    assert _page_url("/shop/katzen/katzenfutter_dose", 2) == (
        "https://www.zooplus.de/shop/katzen/katzenfutter_dose?p=2"
    )


def test_page_url_kategorie_mit_eigenem_query_string():
    """Regressionstest: eine Kategorie-URL mit "?" darf kein zweites "?"
    bekommen, sonst wird die URL kaputt (siehe Chat: genau das war der
    Grund, warum die Rabatt-Suchseite vorher nicht einfach eingetragen
    werden konnte)."""
    category = "/search/results?q=Katze&filters=action%3Dhas_abd%3Bprice_reduced"
    url = _page_url(category, 2)
    assert url == (
        "https://www.zooplus.de/search/results?q=Katze&"
        "filters=action%3Dhas_abd%3Bprice_reduced&p=2"
    )
    assert url.count("?") == 1
