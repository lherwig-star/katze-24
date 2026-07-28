"""Temporaeres Debug-Skript: rohe Product-JSON-LD-Bloecke einer Zooplus-
Kategorieseite ausgeben, um zu pruefen, ob das Rabatt-Badge (siehe Chat -
Screenshot mit "25% Rabatt" bei Felix Soup Time) schon im rohen HTML
steckt oder erst per JavaScript reingerendert wird.

Wird per GitHub Actions ausgefuehrt (zooplus.de ist aus der Sandbox
blockiert), danach wieder entfernt - kein Teil des eigentlichen Crawlers.
"""
import json
import sys

sys.path.insert(0, ".")

from src.http import Fetcher
from src.jsonld import find_by_type

url = "https://www.zooplus.de/shop/katzen/katzenfutter_dose"
fetcher = Fetcher(delay=(1.0, 2.0))
html = fetcher.get(url).text

print(f"HTML-Laenge: {len(html)} Zeichen")

products = list(find_by_type(html, "Product"))
print(f"{len(products)} Product-Bloecke gefunden\n")

# Nach den drei Produkten aus dem Screenshot suchen (mit sichtbarer
# Rabatt-Badge), um deren KOMPLETTEN rohen JSON-Block zu sehen -
# nicht nur die Felder, die wir bisher schon parsen.
keywords = ["felix", "soup", "cosma", "animonda carny"]
shown = 0
for p in products:
    name = str(p.get("name", "")).lower()
    if any(k in name for k in keywords) and shown < 5:
        print("=" * 60)
        print(json.dumps(p, indent=2, ensure_ascii=False))
        shown += 1

if shown == 0:
    print("Keine der gesuchten Produkte auf Seite 1 gefunden - zeige stattdessen die ersten 3 Bloecke komplett:")
    for p in products[:3]:
        print("=" * 60)
        print(json.dumps(p, indent=2, ensure_ascii=False))
