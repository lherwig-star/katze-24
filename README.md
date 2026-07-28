# katze-24 (petdeals)

Ein Bot, der Tierbedarf-Shops crawlt, Preise über Zeit speichert und meldet,
wenn ein Produkt wirklich günstig ist – nicht nur laut Streichpreis vom Shop,
sondern verglichen mit dem eigenen, gemessenen Preisverlauf.

## Wie es funktioniert

```
Crawler (src/crawlers/*.py)
    │  liefert Offer-Objekte (Titel, Preis, URL, ...)
    ▼
Storage (src/storage.py, SQLite)
    │  speichert Angebote + einen Preispunkt pro Tag
    ▼
Deal Engine (src/dealengine.py)
    │  vergleicht aktuellen Preis mit der Historie
    ▼
Notifier (src/notifier.py)
       schickt fertige Nachricht raus (Console / Datei / Telegram)
```

Jeder Shop ist ein eigener Crawler in `src/crawlers/`. Neue Crawler werden
automatisch erkannt – ihr müsst nirgendwo eine Liste pflegen. Das ist
Absicht: so können zwei Leute an zwei Shops arbeiten, ohne sich beim Mergen
in die Quere zu kommen (siehe Abschnitt "Arbeitsteilung" unten).

## Setup (für beide Rechner identisch)

Vorausgesetzt: Python 3.9+ ist installiert (`python3 --version` prüfen).

```bash
git clone <repo-url>
cd petdeals

python3 -m venv venv
source venv/bin/activate        # macOS/Linux
# venv\Scripts\activate          # Windows

pip install -r requirements.txt

cp .env.example .env            # nur ausfüllen, wenn ihr Telegram nutzt
```

Danach immer zuerst `source venv/bin/activate` in einem neuen Terminal.

### Testen, ob alles läuft

```bash
python -m pytest -q
```

Sollte grün sein, ganz ohne Internetzugriff (die Tests rufen keine echten
Shops auf).

## Benutzung

```bash
# Welche Crawler gibt es, welche sind aktiv?
python -m src.main list

# Einen Shop crawlen, Ergebnis in der lokalen SQLite-DB speichern
python -m src.main crawl --shop zooplus --limit 20   # --limit zum schnellen Testen
python -m src.main crawl                              # alle aktiven Shops, ohne Limit

# Aktuelle Deals ansehen (ohne zu verschicken)
python -m src.main deals

# Deals verschicken
python -m src.main send --dry-run           # nur anzeigen, nichts markieren
python -m src.main send --via telegram       # echt verschicken

# Taeglicher Bericht, nach Kategorie (Futter/Streu/Spielzeug/...) gruppiert -
# zur manuellen Review, bevor ihr etwas in den WhatsApp-Kanal kopiert
python -m src.main report --via telegram --top-per-category 5

# Statistik über die eigene Datenbank
python -m src.main stats
```

**Was zaehlt als Deal:** Ausschlaggebend ist, ob der SHOP SELBST das
Produkt als reduziert markiert (z.B. Zooplus' eigenes StrikethroughPrice-
Feld oder Fressnapfs Sale-Kategorie) - nicht mehr die eigene Preishistorie.
Die Historie liefert nur noch einen Zusatz-Hinweis in der Nachricht
("...und das ist sogar Tiefstpreis der letzten 30 Tage"). Details und die
Begründung dafür stehen in `src/dealengine.py`.

### Täglich automatisch crawlen

**Option A – in der Cloud (empfohlen, läuft ohne dass ein Rechner an sein muss):**
`.github/workflows/crawl.yml` crawlt täglich um 6 Uhr UTC über GitHub Actions.
Da GitHub-Actions-Runner nach jedem Lauf wieder leer sind, wird die Preis-
datenbank (`data/petdeals.db`) am Ende jedes Laufs auf einen eigenen Branch
**`data`** committet – bewusst nicht auf `main`, damit der PR-Schutz auf
`main` unberührt bleibt und Code- und Preishistorie sauber getrennt sind.

Manuell testen: auf GitHub unter *Actions → Crawl → Run workflow*.

Aktuelle Preisdaten lokal abholen:
```bash
git fetch origin data
git show origin/data:data/petdeals.db > data/petdeals.db
python -m src.main stats   # zum Prüfen
```

**Option B – lokal per Cron (falls ihr die Cloud-Variante nicht wollt):**
```bash
crontab -e
# Zeile einfügen (crawlt jeden Tag um 8 Uhr):
0 8 * * * cd /pfad/zu/petdeals && venv/bin/python -m src.main crawl >> logs/cron.log 2>&1
```

### Täglicher Bericht (zur manuellen Review)

Nach jedem Cloud-Crawl schickt `.github/workflows/crawl.yml` automatisch
einen Bericht – nach Kategorie gruppiert, mit den besten Deals fertig
formatiert zum Kopieren – an einen **privaten** Telegram-Chat. Das ist
bewusst kein automatischer Versand in den öffentlichen WhatsApp-Kanal:
ihr schaut euch den Bericht an, sucht euch die guten Deals raus und
postet die von Hand.

Einmalig einrichten (dauert ~5 Minuten):
1. In Telegram `@BotFather` anschreiben → `/newbot` → Namen vergeben →
   Token kopieren.
2. Einen privaten Gruppenchat mit euch beiden anlegen, den Bot dort
   reinladen, irgendwas in den Chat schreiben (damit er "gesehen" wird).
3. `https://api.telegram.org/bot<TOKEN>/getUpdates` im Browser öffnen,
   darin `"chat":{"id": ...}` suchen (bei Gruppen negativ, z.B. `-123456`).
4. Auf GitHub: *Settings → Secrets and variables → Actions → New
   repository secret* – zweimal:
   - `TELEGRAM_BOT_TOKEN` = der Token aus Schritt 1
   - `TELEGRAM_CHAT_ID` = die ID aus Schritt 3

Ohne diese beiden Secrets läuft der Crawl trotzdem – der Bericht landet
dann einfach nur im Actions-Log statt bei euch in Telegram (kein
Fehlschlag, siehe `src/main.py::cmd_report`).

Lokal ausprobieren, sobald ihr `.env` ausgefüllt habt (siehe
`.env.example`):
```bash
python -m src.main report --via telegram --top-per-category 5
python -m src.main report                      # ohne Telegram, nur zum Angucken
```

## Einen neuen Shop anbinden

1. `src/crawlers/fressnapf.py` lesen – dort steht eine Schritt-für-Schritt-
   Anleitung inklusive robots.txt-Stand.
2. Kurzfassung: robots.txt prüfen, dann checken ob die Kategorieseite
   JSON-LD (`application/ld+json`) mit Produktdaten enthält:
   ```bash
   curl -sL -A "Mozilla/5.0" "<kategorie-url>" | grep -c '"@type":"Product"'
   ```
   Wenn ja: `src/crawlers/zooplus.py` als Vorlage nehmen, `_walk_products`
   ist bewusst generisch geschrieben und funktioniert oft unverändert.
   Wenn nein: `src/crawlers/demo_books.py` zeigt CSS-Selektoren.
3. Neue Datei `src/crawlers/<shop>.py`, Klasse erbt von `BaseCrawler`,
   `shop = "<name>"` setzen. Wird automatisch erkannt.
4. `enabled = True` erst, wenn `python -m src.main crawl --shop <name>
   --limit 5` sinnvolle Daten liefert.

## Arbeitsteilung zu zweit

Damit ihr euch nicht in die Quere kommt:

- **`src/models.py` nur gemeinsam anfassen** (kurz absprechen, wer was
  braucht). Das ist der Datenvertrag zwischen allen Modulen.
- **Jeder nimmt sich einen anderen Shop** → eigene Datei in
  `src/crawlers/`, keine gemeinsam bearbeitete Datei, praktisch nie
  Merge-Konflikte.
- Branches: `crawler/<shop>` (z. B. `crawler/fressnapf`), PR gegen `main`,
  der andere schaut kurz drüber. GitHub Action (`.github/workflows/tests.yml`)
  lässt die Tests automatisch laufen.
- Wer die Deal-Engine oder den Notifier anfasst, kurz im Chat Bescheid
  sagen – die sind zentral und werden von allen Crawlern genutzt.

## Grenzen, die bewusst gesetzt sind

- **Kein Amazon-Scraping.** Verstößt gegen die Amazon-AGB. Falls gewünscht:
  offizielle PA-API, eigenes Thema.
- **Kein automatisierter WhatsApp-Versand.** Es gibt keine offizielle API
  für Nachrichten in eine Gruppe/Community; inoffizielle Bibliotheken
  (whatsapp-web.js, Baileys) verstoßen gegen die Nutzungsbedingungen und
  die Nummer wird irgendwann gesperrt. Stattdessen: Telegram-Bot (5 Minuten
  Einrichtung, siehe `src/notifier.py`) oder `--via file` und Copy&Paste in
  die WhatsApp-Gruppe.
- **Rate-Limiting nicht aggressiv runterdrehen.** `src/http.py` wartet
  bewusst 2–6 Sekunden zwischen Requests. Das ist der Unterschied zwischen
  "wird toleriert" und "IP gesperrt".
