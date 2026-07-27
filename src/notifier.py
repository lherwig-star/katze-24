"""Versand der Deals.

WICHTIG - zur WhatsApp-Realitaet:
WhatsApp hat keine offizielle API, mit der ein Bot in eine Community oder
Gruppe posten kann. Die Cloud API von Meta ist fuer 1:1-Nachrichten mit
Opt-in und vorab freigegebenen Templates gedacht. Bibliotheken wie
whatsapp-web.js oder Baileys steuern eine echte WhatsApp-Session fern -
das verstoesst gegen die Nutzungsbedingungen und die Nummer fliegt
frueher oder spaeter raus.

Deshalb der pragmatische Aufbau hier:
  console  - Standard, gibt die Nachrichten im Terminal aus
  telegram - funktioniert sofort, offizielle API, 5 Minuten Einrichtung
  file     - schreibt fertige Nachrichten in eine Textdatei, die ihr
             per Copy&Paste in die WhatsApp-Gruppe kippt

Empfehlung: Baut die Pipeline mit `telegram` fertig. Das ist technisch
dasselbe Problem, nur ohne Sperrrisiko. Wenn ihr WhatsApp unbedingt
automatisiert wollt, nehmt eine separate Prepaid-Nummer und rechnet damit,
sie zu verlieren.
"""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path

import requests

from src.models import Deal

log = logging.getLogger(__name__)


def format_deal(deal: Deal) -> str:
    """Deal -> fertige Nachricht."""
    o = deal.offer
    lines = [f"🔥 {o.title}"]

    price = _eur(o.price_cents)
    ref = _eur(deal.ref_price_cents)
    lines.append(f"{price}  (statt {ref})  −{deal.discount_pct:.0f}%")

    if o.price_per_unit_cents and o.unit:
        lines.append(f"Grundpreis: {_eur(round(o.price_per_unit_cents))}/{o.unit}")

    lines.append(deal.reason)
    lines.append(o.url)
    return "\n".join(lines)


class Notifier(ABC):
    @abstractmethod
    def send(self, text: str) -> bool:
        """True bei Erfolg."""


class ConsoleNotifier(Notifier):
    def send(self, text: str) -> bool:
        print("\n" + "─" * 50)
        print(text)
        return True


class FileNotifier(Notifier):
    """Sammelt Nachrichten in einer Datei zum Rauskopieren."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or Path("data") / "zum_versenden.txt"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def send(self, text: str) -> bool:
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(f"\n--- {stamp} ---\n{text}\n")
        return True


class TelegramNotifier(Notifier):
    """Braucht TELEGRAM_BOT_TOKEN und TELEGRAM_CHAT_ID in der .env.

    Einrichtung:
      1. In Telegram @BotFather anschreiben -> /newbot -> Token kopieren
      2. Bot in deine Gruppe einladen, dort irgendwas schreiben
      3. https://api.telegram.org/bot<TOKEN>/getUpdates aufrufen,
         die chat.id (negativ bei Gruppen) rauskopieren
    """

    def __init__(self) -> None:
        self.token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
        if not (self.token and self.chat_id):
            raise SystemExit(
                "TELEGRAM_BOT_TOKEN und TELEGRAM_CHAT_ID fehlen in der .env - "
                "siehe .env.example"
            )

    def send(self, text: str) -> bool:
        try:
            resp = requests.post(
                f"https://api.telegram.org/bot{self.token}/sendMessage",
                json={
                    "chat_id": self.chat_id,
                    "text": text,
                    "disable_web_page_preview": False,
                },
                timeout=15,
            )
            resp.raise_for_status()
            return True
        except requests.RequestException as exc:
            log.error("Telegram-Versand fehlgeschlagen: %s", exc)
            return False


def get_notifier(name: str) -> Notifier:
    options = {
        "console": ConsoleNotifier,
        "file": FileNotifier,
        "telegram": TelegramNotifier,
    }
    if name not in options:
        raise SystemExit(f"Unbekannter Notifier {name!r}. Moeglich: {', '.join(options)}")
    return options[name]()


def _eur(cents: int) -> str:
    return f"{cents / 100:.2f} €".replace(".", ",")
