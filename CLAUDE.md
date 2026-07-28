# petdeals

Bot, der Tierbedarf-Shops crawlt und Produkte meldet, die der SHOP SELBST
als reduziert markiert hat (nicht gegen die eigene Preishistorie - siehe
src/dealengine.py fuer die Begruendung des Kurswechsels).

## Regeln fuer Claude Code in diesem Repo

- **`src/models.py` nur nach Absprache aendern.** Das ist der Vertrag
  zwischen allen Modulen (Offer, Deal). Wer hier unabgesprochen Felder
  aendert, bricht den Code des anderen.
- **Preise immer `int` in Cent.** Nie `float` fuer Geld.
- **Neuer Shop = neue Datei in `src/crawlers/`.** Keine zentrale Liste
  pflegen, die Registry (`src/crawlers/base.py`) discovered automatisch
  ueber `__init_subclass__`. Siehe `src/crawlers/zooplus.py` als Vorlage
  fuer JSON-LD-Shops, `src/crawlers/demo_books.py` fuer CSS-Selektor-Shops.
- **Vor einem neuen Crawler: robots.txt lesen und pruefen, ob JSON-LD
  (`application/ld+json`) auf der Seite Produktdaten enthaelt.** Das ist
  stabiler als CSS-Selektoren und aendert sich fast nie (SEO-relevant).
  Erst wenn das fehlt: CSS-Selektoren oder eine interne JSON-API nutzen
  (Netzwerk-Tab im Browser, Fetch/XHR-Filter).
- **Kein Amazon-Scraping.** Verstoss gegen die Amazon-AGB, technisch auch
  hart (Bot-Schutz). Wenn Amazon gewuenscht ist: PA-API, eigenes Thema.
- **Rate-Limiting nie umgehen.** `src/http.py::Fetcher` ist die einzige
  Stelle, die HTTP-Requests macht. Verzoegerung nicht runterdrehen, nur
  um schneller zu testen - dafuer gibt es `--limit`.
- **Kein WhatsApp-Automatisierungs-Client** (whatsapp-web.js, Baileys o.ae.).
  Verstoesst gegen WhatsApp-ToS und die Nummer fliegt raus. Notifier-Optionen
  siehe `src/notifier.py` (aktuell: console, file, telegram).
- **Tests vor jedem Commit:** `python -m pytest -q`. Contract-Tests in
  `tests/test_contract.py` gelten fuer jeden Crawler automatisch.
- Python 3.9 auf beiden Rechnern - **keine 3.10+-only Syntax** (kein
  `slots=True` bei dataclasses, kein `match`-Statement).

## Aktueller Stand

- `zooplus`: echter Crawler, laeuft (JSON-LD auf der Kategorieseite).
- `fressnapf`: echter Crawler, laeuft (zweistufig: ItemList-JSON-LD auf der
  Kategorieseite liefert Produkt-URLs, Preis kommt vom Product-JSON-LD der
  einzelnen Produktseite - siehe Docstring in `src/crawlers/fressnapf.py`
  fuer die Recherche dahinter. Deckt ca. 49 Produkte pro Kategorie ab,
  keine JS-Pagination).
- `demo_books`: Uebungs-Crawler gegen books.toscrape.com, nicht produktiv.
- `src/jsonld.py`: gemeinsame JSON-LD-Hilfsfunktionen (von zooplus.py und
  fressnapf.py genutzt) - fuer den naechsten Shop zuerst hier nachsehen.
- Taeglicher Crawl laeuft ueber `.github/workflows/crawl.yml` (GitHub
  Actions, Cloud). Preisdaten landen auf dem Branch `data`, NICHT auf
  `main` - main bleibt PR-geschuetzter Code, `data` ist reine
  Bot-Historie. Lokal abholen: siehe README, Abschnitt "Automatisch
  crawlen".
- `Offer.category` (z.B. "Futter", "Streu", "Spielzeug") wird von jedem
  Crawler selbst vergeben (siehe CATEGORIES-Listen in den jeweiligen
  Dateien). Unbekannt/None landet im Bericht unter "Sonstiges".
- `src/report.py` baut den taeglichen, nach Kategorie gruppierten Bericht
  zur manuellen Review (`python -m src.main report`). Wird nach jedem
  Cloud-Crawl automatisch per Telegram an einen PRIVATEN Chat geschickt -
  bewusst kein automatischer Versand in den oeffentlichen WhatsApp-Kanal.
  Secrets `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` siehe README.
