"""SQLite-Speicher: Angebote, Preishistorie, Versand-Log.

SQLite reicht hier voellig - eine Datei, kein Server, laeuft auf beiden
MacBooks identisch. Wenn ihr irgendwann Millionen Zeilen habt, tauscht ihr
diese Datei gegen Postgres aus; der Rest des Codes merkt davon nichts.

WICHTIG: data/petdeals.db gehoert NICHT ins Git (steht in .gitignore).
Jeder von euch hat seine eigene lokale Datenbank.
"""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import Iterable
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.models import Offer

log = logging.getLogger(__name__)

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "petdeals.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS offers (
    uid              TEXT PRIMARY KEY,
    shop             TEXT NOT NULL,
    product_id       TEXT NOT NULL,
    title            TEXT NOT NULL,
    brand            TEXT,
    url              TEXT NOT NULL,
    image_url        TEXT,
    price_cents      INTEGER NOT NULL,
    list_price_cents INTEGER,
    is_marked_down   INTEGER NOT NULL DEFAULT 0,
    category         TEXT,
    unit_amount      REAL,
    unit             TEXT,
    available        INTEGER NOT NULL DEFAULT 1,
    last_seen        TEXT NOT NULL
);

-- Eine Zeile pro Produkt und Tag. Das ist das Herzstueck: ohne Historie
-- kann man keinen echten Rabatt von einem gefaketen Streichpreis trennen.
CREATE TABLE IF NOT EXISTS price_points (
    uid         TEXT NOT NULL,
    day         TEXT NOT NULL,
    price_cents INTEGER NOT NULL,
    PRIMARY KEY (uid, day)
);
CREATE INDEX IF NOT EXISTS idx_price_points_uid ON price_points(uid);

-- Damit derselbe Deal nicht dreimal in der Gruppe landet.
CREATE TABLE IF NOT EXISTS sent_deals (
    uid         TEXT NOT NULL,
    sent_at     TEXT NOT NULL,
    price_cents INTEGER NOT NULL,
    PRIMARY KEY (uid, sent_at)
);
"""


class Store:
    def __init__(self, path: Path = DB_PATH) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self._migrate()
        self.conn.commit()

    def _migrate(self) -> None:
        """CREATE TABLE IF NOT EXISTS legt neue Spalten nicht in bestehenden
        Datenbanken an - hier nachtraeglich ergaenzen, damit alte
        petdeals.db-Dateien (lokal oder auf dem data-Branch) weiterlaufen."""
        columns = {row["name"] for row in self.conn.execute("PRAGMA table_info(offers)")}
        if "is_marked_down" not in columns:
            self.conn.execute(
                "ALTER TABLE offers ADD COLUMN is_marked_down INTEGER NOT NULL DEFAULT 0"
            )
        if "category" not in columns:
            self.conn.execute("ALTER TABLE offers ADD COLUMN category TEXT")

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "Store":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # ---------- schreiben ----------

    def save_offers(self, offers: Iterable[Offer]) -> int:
        """Angebote speichern und je einen Preispunkt pro Tag schreiben."""
        count = 0
        for offer in offers:
            day = offer.seen_at.astimezone(timezone.utc).date().isoformat()
            self.conn.execute(
                """
                INSERT INTO offers (uid, shop, product_id, title, brand, url,
                    image_url, price_cents, list_price_cents, is_marked_down,
                    category, unit_amount, unit, available, last_seen)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(uid) DO UPDATE SET
                    title=excluded.title,
                    price_cents=excluded.price_cents,
                    list_price_cents=excluded.list_price_cents,
                    is_marked_down=excluded.is_marked_down,
                    category=excluded.category,
                    available=excluded.available,
                    last_seen=excluded.last_seen
                """,
                (
                    offer.uid, offer.shop, offer.product_id, offer.title,
                    offer.brand, offer.url, offer.image_url, offer.price_cents,
                    offer.list_price_cents, int(offer.is_marked_down),
                    offer.category, offer.unit_amount, offer.unit,
                    int(offer.available), offer.seen_at.isoformat(),
                ),
            )
            # Mehrmals am Tag crawlen ist erlaubt - wir behalten den
            # niedrigsten Preis des Tages.
            self.conn.execute(
                """
                INSERT INTO price_points (uid, day, price_cents) VALUES (?,?,?)
                ON CONFLICT(uid, day) DO UPDATE SET
                    price_cents = MIN(price_points.price_cents, excluded.price_cents)
                """,
                (offer.uid, day, offer.price_cents),
            )
            count += 1
        self.conn.commit()
        return count

    def mark_sent(self, uid: str, price_cents: int) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO sent_deals (uid, sent_at, price_cents) "
            "VALUES (?,?,?)",
            (uid, datetime.now(timezone.utc).isoformat(), price_cents),
        )
        self.conn.commit()

    # ---------- lesen ----------

    def price_history(self, uid: str, days: int = 90) -> list[int]:
        """Preise der letzten N Tage, ohne heute."""
        since = (datetime.now(timezone.utc).date() - timedelta(days=days)).isoformat()
        today = datetime.now(timezone.utc).date().isoformat()
        rows = self.conn.execute(
            "SELECT price_cents FROM price_points "
            "WHERE uid=? AND day>=? AND day<? ORDER BY day",
            (uid, since, today),
        ).fetchall()
        return [r["price_cents"] for r in rows]

    def was_sent_recently(self, uid: str, days: int = 14) -> bool:
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        row = self.conn.execute(
            "SELECT 1 FROM sent_deals WHERE uid=? AND sent_at>=? LIMIT 1",
            (uid, since),
        ).fetchone()
        return row is not None

    def current_offers(self, shop: str | None = None) -> list[Offer]:
        sql = "SELECT * FROM offers WHERE available=1"
        params: tuple = ()
        if shop:
            sql += " AND shop=?"
            params = (shop,)
        return [_row_to_offer(r) for r in self.conn.execute(sql, params)]

    def stats(self) -> dict[str, int]:
        q = self.conn.execute
        return {
            "angebote": q("SELECT COUNT(*) c FROM offers").fetchone()["c"],
            "preispunkte": q("SELECT COUNT(*) c FROM price_points").fetchone()["c"],
            "tage_historie": q(
                "SELECT COUNT(DISTINCT day) c FROM price_points"
            ).fetchone()["c"],
            "verschickt": q("SELECT COUNT(*) c FROM sent_deals").fetchone()["c"],
        }


def _row_to_offer(row: sqlite3.Row) -> Offer:
    return Offer(
        shop=row["shop"],
        product_id=row["product_id"],
        title=row["title"],
        price_cents=row["price_cents"],
        url=row["url"],
        brand=row["brand"],
        list_price_cents=row["list_price_cents"],
        is_marked_down=bool(row["is_marked_down"]),
        category=row["category"],
        image_url=row["image_url"],
        unit_amount=row["unit_amount"],
        unit=row["unit"],
        available=bool(row["available"]),
        seen_at=datetime.fromisoformat(row["last_seen"]),
    )
