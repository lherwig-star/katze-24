"""Ein gemeinsamer HTTP-Client fuer alle Crawler.

Warum zentral? Damit Rate-Limiting, User-Agent und Retries an EINER Stelle
stehen. Wenn jeder Crawler sein eigenes requests.get() macht, hat man nach
drei Wochen drei verschiedene Verhalten und eine IP-Sperre.
"""

from __future__ import annotations

import logging
import random
import time

import requests
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

# Ehrlicher User-Agent: sagt, wer wir sind. Shops sperren nicht den Bot,
# der sich zu erkennen gibt und langsam laeuft - sie sperren den, der
# 50 Requests/Sekunde feuert und sich als Chrome ausgibt.
USER_AGENT = "petdeals-bot/0.1 (Hobbyprojekt; Kontakt: bitte-in-.env-eintragen)"

DEFAULT_DELAY = (2.0, 4.0)  # Sekunden zwischen zwei Requests, zufaellig
TIMEOUT = 20
MAX_RETRIES = 3


class Fetcher:
    """Holt Seiten - hoeflich, mit Pause und Wiederholung bei Fehlern."""

    def __init__(
        self,
        delay: tuple[float, float] = DEFAULT_DELAY,
        user_agent: str = USER_AGENT,
    ) -> None:
        self.delay = delay
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": user_agent,
                "Accept-Language": "de-DE,de;q=0.9",
            }
        )
        self._last_request = 0.0

    def _wait(self) -> None:
        pause = random.uniform(*self.delay)
        elapsed = time.monotonic() - self._last_request
        if elapsed < pause:
            time.sleep(pause - elapsed)
        self._last_request = time.monotonic()

    def get(self, url: str, **kwargs) -> requests.Response:
        last_error: Exception | None = None
        for attempt in range(1, MAX_RETRIES + 1):
            self._wait()
            try:
                resp = self.session.get(url, timeout=TIMEOUT, **kwargs)
                if resp.status_code == 429:
                    wait = 30 * attempt
                    log.warning("429 von %s - warte %ss", url, wait)
                    time.sleep(wait)
                    continue
                resp.raise_for_status()
                return resp
            except requests.RequestException as exc:
                last_error = exc
                log.warning("Versuch %s/%s fehlgeschlagen fuer %s: %s",
                            attempt, MAX_RETRIES, url, exc)
                time.sleep(2**attempt)
        raise RuntimeError(f"Konnte {url} nicht laden") from last_error

    def soup(self, url: str, **kwargs) -> BeautifulSoup:
        """Seite holen und direkt als BeautifulSoup zurueckgeben."""
        return BeautifulSoup(self.get(url, **kwargs).text, "lxml")
